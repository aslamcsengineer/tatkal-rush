import asyncio
import time

from sqlalchemy import text
from database import AsyncSessionLocal


SIMULATION_SEATS = 10


# ============================================================
# CREATE / RESET SIMULATION TABLES
# ============================================================

async def prepare_simulation():
    """
    Creates isolated simulation tables and resets them before
    every rush test.

    This does NOT modify:
        seats
        reservations
        bookings
        booking_requests
    """

    async with AsyncSessionLocal() as session:

        async with session.begin():

            # -----------------------------------------------
            # CREATE SIMULATION SEATS TABLE
            # -----------------------------------------------

            await session.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS simulation_seats (
                        id SERIAL PRIMARY KEY,
                        seat_number VARCHAR(20) NOT NULL UNIQUE,
                        status VARCHAR(20) NOT NULL
                            DEFAULT 'AVAILABLE'
                    )
                """)
            )

            # -----------------------------------------------
            # CREATE SIMULATION REQUESTS TABLE
            # -----------------------------------------------

            await session.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS simulation_requests (
                        id BIGSERIAL PRIMARY KEY,
                        user_id VARCHAR(100) NOT NULL,
                        seat_number VARCHAR(20),
                        status VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP
                            DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )

            # -----------------------------------------------
            # RESET PREVIOUS SIMULATION DATA
            # -----------------------------------------------

            await session.execute(
                text("""
                    TRUNCATE TABLE simulation_requests
                    RESTART IDENTITY
                """)
            )

            await session.execute(
                text("""
                    TRUNCATE TABLE simulation_seats
                    RESTART IDENTITY
                """)
            )

            # -----------------------------------------------
            # CREATE 10 ISOLATED SIMULATION SEATS
            # -----------------------------------------------

            for number in range(1, SIMULATION_SEATS + 1):

                await session.execute(
                    text("""
                        INSERT INTO simulation_seats (
                            seat_number,
                            status
                        )
                        VALUES (
                            :seat_number,
                            'AVAILABLE'
                        )
                    """),
                    {
                        "seat_number":
                            f"SIM-{number:02d}"
                    }
                )


# ============================================================
# SINGLE ARTIFICIAL USER
# ============================================================

async def simulate_user(user_number: int):
    """
    Represents one artificial Tatkal user.

    Every user gets its own database transaction.

    FOR UPDATE SKIP LOCKED prevents two concurrent
    transactions from claiming the same simulation seat.
    """

    user_id = f"SIM-USER-{user_number:05d}"

    async with AsyncSessionLocal() as session:

        try:

            async with session.begin():

                # -------------------------------------------
                # LOCK ONE AVAILABLE SEAT
                # -------------------------------------------

                result = await session.execute(
                    text("""
                        SELECT
                            id,
                            seat_number

                        FROM simulation_seats

                        WHERE status = 'AVAILABLE'

                        ORDER BY id

                        LIMIT 1

                        FOR UPDATE SKIP LOCKED
                    """)
                )

                seat = result.mappings().first()

                # -------------------------------------------
                # SOLD OUT
                # -------------------------------------------

                if seat is None:

                    request_result = await session.execute(
                        text("""
                            INSERT INTO simulation_requests (
                                user_id,
                                seat_number,
                                status
                            )
                            VALUES (
                                :user_id,
                                NULL,
                                'SOLD_OUT'
                            )
                            RETURNING id
                        """),
                        {
                            "user_id": user_id
                        }
                    )

                    queue_number = (
                        request_result.scalar_one()
                    )

                    return {
                        "success": False,
                        "user_id": user_id,
                        "queue_number": queue_number,
                        "status": "SOLD_OUT",
                        "seat": None,
                    }

                # -------------------------------------------
                # SEAT FOUND
                # -------------------------------------------

                seat_id = seat["id"]
                seat_number = seat["seat_number"]

                # -------------------------------------------
                # MARK SEAT HELD
                # -------------------------------------------

                await session.execute(
                    text("""
                        UPDATE simulation_seats

                        SET status = 'HELD'

                        WHERE id = :seat_id
                          AND status = 'AVAILABLE'
                    """),
                    {
                        "seat_id": seat_id
                    }
                )

                # -------------------------------------------
                # RECORD WINNING REQUEST
                # -------------------------------------------

                request_result = await session.execute(
                    text("""
                        INSERT INTO simulation_requests (
                            user_id,
                            seat_number,
                            status
                        )
                        VALUES (
                            :user_id,
                            :seat_number,
                            'ALLOCATED'
                        )
                        RETURNING id
                    """),
                    {
                        "user_id": user_id,
                        "seat_number": seat_number,
                    }
                )

                queue_number = (
                    request_result.scalar_one()
                )

                return {
                    "success": True,
                    "user_id": user_id,
                    "queue_number": queue_number,
                    "status": "ALLOCATED",
                    "seat": seat_number,
                }

        except Exception as error:

            await session.rollback()

            return {
                "success": False,
                "user_id": user_id,
                "queue_number": None,
                "status": "ERROR",
                "seat": None,
                "error": str(error),
            }


# ============================================================
# RUN COMPLETE RUSH SIMULATION
# ============================================================

async def run_simulation(
    users: int = 1000,
    concurrency: int = 200,
):
    """
    Runs an isolated high-concurrency Tatkal simulation.

    Example:

        users       = 1000
        concurrency = 200
        seats       = 10

    Expected concurrency-safe result:

        10 allocated
        990 rejected
        0 duplicate seats
    """

    # --------------------------------------------------------
    # SAFETY LIMITS
    # --------------------------------------------------------

    users = max(1, min(users, 10000))
    concurrency = max(
        1,
        min(concurrency, 500)
    )

    # --------------------------------------------------------
    # RESET SIMULATION
    # --------------------------------------------------------

    await prepare_simulation()

    semaphore = asyncio.Semaphore(concurrency)

    # --------------------------------------------------------
    # CONTROL CONCURRENCY
    # --------------------------------------------------------

    async def controlled_user(number):

        async with semaphore:

            return await simulate_user(number)

    # --------------------------------------------------------
    # START TIMER
    # --------------------------------------------------------

    started = time.perf_counter()

    tasks = [
        controlled_user(number)
        for number in range(1, users + 1)
    ]

    results = await asyncio.gather(*tasks)

    execution_time = (
        time.perf_counter() - started
    )

    # ========================================================
    # ANALYSIS
    # ========================================================

    successful = [
        item
        for item in results
        if item.get("success") is True
    ]

    rejected = [
        item
        for item in results
        if item.get("status") == "SOLD_OUT"
    ]

    errors = [
        item
        for item in results
        if item.get("status") == "ERROR"
    ]

    allocated_seats = [
        item["seat"]
        for item in successful
        if item.get("seat")
    ]

    queue_numbers = [
        item["queue_number"]
        for item in results
        if item.get("queue_number") is not None
    ]

    # --------------------------------------------------------
    # DUPLICATE SEAT CHECK
    # --------------------------------------------------------

    duplicate_seats = {}

    for seat in allocated_seats:

        count = allocated_seats.count(seat)

        if count > 1:
            duplicate_seats[seat] = count

    # --------------------------------------------------------
    # DUPLICATE QUEUE CHECK
    # --------------------------------------------------------

    duplicate_queue_count = (
        len(queue_numbers)
        - len(set(queue_numbers))
    )

    # --------------------------------------------------------
    # DATABASE VERIFICATION
    # --------------------------------------------------------

    async with AsyncSessionLocal() as session:

        seat_result = await session.execute(
            text("""
                SELECT
                    seat_number,
                    status

                FROM simulation_seats

                ORDER BY id
            """)
        )

        database_seats = [
            dict(row)
            for row
            in seat_result.mappings().all()
        ]

        request_result = await session.execute(
            text("""
                SELECT
                    COUNT(*) AS total,

                    COUNT(*) FILTER (
                        WHERE status = 'ALLOCATED'
                    ) AS allocated,

                    COUNT(*) FILTER (
                        WHERE status = 'SOLD_OUT'
                    ) AS sold_out

                FROM simulation_requests
            """)
        )

        database_counts = dict(
            request_result.mappings().one()
        )

    # --------------------------------------------------------
    # FINAL VERIFICATION
    # --------------------------------------------------------

    zero_double_booking = (
        len(duplicate_seats) == 0
    )

    unique_queue_ids = (
        duplicate_queue_count == 0
    )

    exactly_expected_winners = (
        len(successful)
        == min(users, SIMULATION_SEATS)
    )

    no_request_errors = (
        len(errors) == 0
    )

    consistency_pass = (
        zero_double_booking
        and unique_queue_ids
        and exactly_expected_winners
        and no_request_errors
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "success": True,

        "configuration": {
            "artificial_users": users,
            "concurrency": concurrency,
            "physical_seats": SIMULATION_SEATS,
        },

        "results": {
            "total_requests": len(results),

            "successful_holds":
                len(successful),

            "rejected_requests":
                len(rejected),

            "unique_seats_allocated":
                len(set(allocated_seats)),

            "duplicate_seat_allocations":
                len(duplicate_seats),

            "queue_ids_issued":
                len(queue_numbers),

            "duplicate_queue_ids":
                duplicate_queue_count,

            "request_errors":
                len(errors),

            "execution_time_seconds":
                round(execution_time, 2),
        },

        "allocated_seats":
            allocated_seats,

        "winning_queue_numbers": [
            item["queue_number"]
            for item in successful
        ],

        "duplicate_details":
            duplicate_seats,

        "database_verification": {
            "requests":
                database_counts,

            "seats":
                database_seats,
        },

        "verification": {
            "consistency":
                "PASS"
                if consistency_pass
                else "FAIL",

            "zero_double_booking":
                zero_double_booking,

            "unique_queue_ids":
                unique_queue_ids,

            "expected_winner_count":
                exactly_expected_winners,

            "no_request_errors":
                no_request_errors,
        },
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    async def main():

        print()
        print("=" * 64)
        print("       TATKAL RUSH ISOLATED SIMULATION")
        print("=" * 64)

        result = await run_simulation(
            users=1000,
            concurrency=200,
        )

        config = result["configuration"]
        stats = result["results"]
        verify = result["verification"]

        print(
            f"Artificial users    : "
            f"{config['artificial_users']}"
        )

        print(
            f"Concurrency         : "
            f"{config['concurrency']}"
        )

        print(
            f"Simulation seats    : "
            f"{config['physical_seats']}"
        )

        print("-" * 64)

        print(
            f"Successful holds    : "
            f"{stats['successful_holds']}"
        )

        print(
            f"Rejected requests   : "
            f"{stats['rejected_requests']}"
        )

        print(
            f"Unique seats        : "
            f"{stats['unique_seats_allocated']}"
        )

        print(
            f"Duplicate seats     : "
            f"{stats['duplicate_seat_allocations']}"
        )

        print(
            f"Queue IDs issued    : "
            f"{stats['queue_ids_issued']}"
        )

        print(
            f"Duplicate queue IDs : "
            f"{stats['duplicate_queue_ids']}"
        )

        print(
            f"Request errors      : "
            f"{stats['request_errors']}"
        )

        print(
            f"Execution time      : "
            f"{stats['execution_time_seconds']} seconds"
        )

        print("-" * 64)

        print(
            "Consistency         :",
            verify["consistency"],
        )

        print(
            "Zero double booking :",
            verify["zero_double_booking"],
        )

        print(
            "Unique queue IDs    :",
            verify["unique_queue_ids"],
        )

        print("=" * 64)

    asyncio.run(main())