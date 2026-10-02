import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from database import AsyncSessionLocal
from simulation import run_simulation


# ============================================================
# CONFIGURATION
# ============================================================

RESERVATION_SECONDS = 30


# ============================================================
# REQUEST MODEL
# ============================================================

class BookingRequest(BaseModel):
    user_id: str


# ============================================================
# AUTOMATIC EXPIRY WORKER
# ============================================================

async def auto_expire_worker():

    while True:

        try:

            async with AsyncSessionLocal() as session:

                async with session.begin():

                    result = await session.execute(
                        text("""
                            SELECT
                            id,
                            user_id,
                            seat_id
                        FROM reservations
                            WHERE status = 'HELD'
                              AND expires_at <= CURRENT_TIMESTAMP
                            FOR UPDATE SKIP LOCKED
                        """)
                    )

                    expired = result.mappings().all()

                    for reservation in expired:

                        # Mark reservation as expired
                        await session.execute(
                            text("""
                                UPDATE reservations
                                SET status = 'EXPIRED'
                                WHERE id = :reservation_id
                                  AND status = 'HELD'
                            """),
                            {
                                "reservation_id":
                                    reservation["id"]
                            }
                        )

                        # Release the seat
                        await session.execute(
                            text("""
                                UPDATE seats
                                SET status = 'AVAILABLE'
                                WHERE id = :seat_id
                                  AND status = 'HELD'
                            """),
                            {
                                "seat_id":
                                    reservation["seat_id"]
                            }
                        )
                        # ----------------------------------------
                        # QUEUE -> EXPIRED
                        # ----------------------------------------

                        await session.execute(
                            text("""
                                UPDATE booking_requests
                                SET status = 'EXPIRED'
                                WHERE id = (
                                    SELECT id
                                    FROM booking_requests
                                    WHERE user_id = :user_id
                                      AND status = 'ALLOCATED'
                                    ORDER BY id DESC
                                    LIMIT 1
                                )
                            """),
                            {
                                "user_id": reservation["user_id"]
                            }
                        )

                    if expired:

                        print(
                            f"AUTO-EXPIRY: "
                            f"Released {len(expired)} seat(s)"
                        )

        except Exception as e:

            print(
                "AUTO-EXPIRY ERROR:",
                str(e)
            )

        await asyncio.sleep(1)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    expiry_task = asyncio.create_task(
        auto_expire_worker()
    )

    print(
        "Tatkal automatic expiry worker started"
    )

    yield

    expiry_task.cancel()

    try:
        await expiry_task
    except asyncio.CancelledError:
        pass

    print(
        "Tatkal automatic expiry worker stopped"
    )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Tatkal Rush API",
    description=(
        "Concurrency-safe Tatkal railway "
        "booking prototype"
    ),
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://tatkal-rush.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "project": "Tatkal Rush",
        "status": "running",
        "reservation_timeout_seconds":
            RESERVATION_SECONDS,
        "concurrency_control":
            "PostgreSQL FOR UPDATE SKIP LOCKED"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():

    try:

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                text("""
                    SELECT
                        current_database(),
                        version()
                """)
            )

            database_name, postgres_version = (
                result.one()
            )

        return {
            "status": "healthy",
            "database": database_name,
            "postgres": postgres_version
        }

    except Exception as e:

        return {
            "status": "unhealthy",
            "error": str(e)
        }


# ============================================================
# GET ALL SEATS
# ============================================================

@app.get("/seats")
async def get_seats():

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            text("""
                SELECT
                    id,
                    seat_number,
                    status
                FROM seats
                ORDER BY id
            """)
        )

        seats = result.mappings().all()

    return {
        "total": len(seats),
        "seats": [
            dict(seat)
            for seat in seats
        ]
    }


# ============================================================
# BOOK / HOLD SEAT
#
# Queue number:
# Records request arrival/registration order.
#
# FOR UPDATE SKIP LOCKED:
# Prevents competing transactions from allocating the
# same seat.
# ============================================================

@app.post("/book")
async def book_seat(request: BookingRequest):

    async with AsyncSessionLocal() as session:

        try:

            async with session.begin():

                # =================================================
                # STEP 1
                # REGISTER REQUEST
                # =================================================

                queue_result = await session.execute(
                    text("""
                        INSERT INTO booking_requests (
                            user_id,
                            status
                        )
                        VALUES (
                            :user_id,
                            'WAITING'
                        )
                        RETURNING id
                    """),
                    {
                        "user_id":
                            request.user_id
                    }
                )

                queue_number = (
                    queue_result.scalar_one()
                )

                # Store the queue number
                await session.execute(
                    text("""
                        UPDATE booking_requests
                        SET queue_number =
                            :queue_number
                        WHERE id =
                            :queue_number
                    """),
                    {
                        "queue_number":
                            queue_number
                    }
                )

                # =================================================
                # STEP 2
                # FIND + LOCK AVAILABLE SEAT
                # =================================================

                seat_result = await session.execute(
                    text("""
                        SELECT
                            id,
                            seat_number
                        FROM seats
                        WHERE status = 'AVAILABLE'
                        ORDER BY id
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    """)
                )

                seat = (
                    seat_result
                    .mappings()
                    .first()
                )

                # =================================================
                # NO SEAT AVAILABLE
                # =================================================

                if seat is None:

                    await session.execute(
                        text("""
                            UPDATE booking_requests
                            SET status = 'SOLD_OUT'
                            WHERE id =
                                :queue_number
                        """),
                        {
                            "queue_number":
                                queue_number
                        }
                    )

                    return {
                        "success": False,
                        "user_id":
                            request.user_id,
                        "queue_number":
                            queue_number,
                        "status":
                            "SOLD_OUT",
                        "message":
                            "No Tatkal seats available"
                    }

                seat_id = seat["id"]

                seat_number = (
                    seat["seat_number"]
                )

                # =================================================
                # STEP 3
                # CREATE PAYMENT DEADLINE
                # =================================================

                expires_at = (
    datetime.now()
    + timedelta(
        seconds=RESERVATION_SECONDS
    )
)

                # =================================================
                # STEP 4
                # HOLD SEAT
                # =================================================

                await session.execute(
                    text("""
                        UPDATE seats
                        SET status = 'HELD'
                        WHERE id = :seat_id
                    """),
                    {
                        "seat_id":
                            seat_id
                    }
                )

                # =================================================
                # STEP 5
                # CREATE RESERVATION
                # =================================================

                reservation_result = (
                    await session.execute(
                        text("""
                            INSERT INTO reservations (
                                user_id,
                                seat_id,
                                status,
                                expires_at
                            )
                            VALUES (
                                :user_id,
                                :seat_id,
                                'HELD',
                                :expires_at
                            )
                            RETURNING id
                        """),
                        {
                            "user_id":
                                request.user_id,

                            "seat_id":
                                seat_id,

                            "expires_at":
                                expires_at
                        }
                    )
                )

                reservation_id = (
                    reservation_result
                    .scalar_one()
                )

                # =================================================
                # STEP 6
                # QUEUE REQUEST ALLOCATED
                # =================================================

                await session.execute(
                    text("""
                        UPDATE booking_requests
                        SET status = 'ALLOCATED'
                        WHERE id =
                            :queue_number
                    """),
                    {
                        "queue_number":
                            queue_number
                    }
                )

            return {
                "success": True,
                "user_id":
                    request.user_id,
                "queue_number":
                    queue_number,
                "seat":
                    seat_number,
                "reservation_id":
                    reservation_id,
                "status":
                    "HELD",
                "expires_in_seconds":
                    RESERVATION_SECONDS
            }

        except Exception as e:

            await session.rollback()

            return {
                "success": False,
                "user_id":
                    request.user_id,
                "error":
                    str(e)
            }


# ============================================================
# PAYMENT SUCCESS
# ============================================================

@app.post(
    "/payment/{reservation_id}/success"
)
async def payment_success(
    reservation_id: int
):

    async with AsyncSessionLocal() as session:

        try:

            async with session.begin():

                result = await session.execute(
                    text("""
                        SELECT
                            r.id,
                            r.user_id,
                            r.seat_id,
                            r.status,
                            r.expires_at,
                            s.seat_number

                        FROM reservations r

                        JOIN seats s
                          ON s.id = r.seat_id

                        WHERE r.id =
                            :reservation_id

                        FOR UPDATE OF r
                    """),
                    {
                        "reservation_id":
                            reservation_id
                    }
                )

                reservation = (
                    result
                    .mappings()
                    .first()
                )

                # ----------------------------------------
                # RESERVATION NOT FOUND
                # ----------------------------------------

                if reservation is None:

                    return {
                        "success": False,
                        "message":
                            "Reservation not found"
                    }

                # ----------------------------------------
                # ALREADY PROCESSED
                # ----------------------------------------

                if (
                    reservation["status"]
                    != "HELD"
                ):

                    return {
                        "success": False,
                        "message":
                            "Reservation is already "
                            + reservation["status"]
                    }

                now = datetime.now()
                # PAYMENT WINDOW EXPIRED
                # ----------------------------------------

                if (
                    reservation["expires_at"]
                    <= now
                ):

                    await session.execute(
                        text("""
                            UPDATE reservations
                            SET status = 'EXPIRED'
                            WHERE id =
                                :reservation_id
                              AND status = 'HELD'
                        """),
                        {
                            "reservation_id":
                                reservation_id
                        }
                    )

                    await session.execute(
                        text("""
                            UPDATE seats
                            SET status = 'AVAILABLE'
                            WHERE id = :seat_id
                              AND status = 'HELD'
                        """),
                        {
                            "seat_id":
                                reservation[
                                    "seat_id"
                                ]
                        }
                    )
                    # ----------------------------------------
                    # QUEUE -> EXPIRED
                    # ----------------------------------------

                    await session.execute(
                        text("""
                            UPDATE booking_requests
                            SET status = 'EXPIRED'
                            WHERE id = (
                                SELECT id
                                FROM booking_requests
                                WHERE user_id = :user_id
                                  AND status = 'ALLOCATED'
                                ORDER BY id DESC
                                LIMIT 1
                            )
                        """),
                        {
                            "user_id": reservation["user_id"]
                        }
                    )

                    return {
                        "success": False,
                        "message":
                            "Payment window expired",
                        "seat":
                            reservation[
                                "seat_number"
                            ]
                    }

                # ----------------------------------------
       
                # ----------------------------------------
                # RESERVATION -> BOOKED
                # ----------------------------------------

                await session.execute(
                    text("""
                        UPDATE reservations
                        SET status = 'BOOKED'
                        WHERE id =
                            :reservation_id
                          AND status = 'HELD'
                    """),
                    {
                        "reservation_id":
                            reservation_id
                    }
                )

                # ----------------------------------------
                # SEAT -> BOOKED
                # ----------------------------------------

                await session.execute(
                    text("""
                        UPDATE seats
                        SET status = 'BOOKED'
                        WHERE id = :seat_id
                          AND status = 'HELD'
                    """),
                    {
                        "seat_id":
                            reservation[
                                "seat_id"
                            ]
                    }
                )

                # ----------------------------------------
                # CREATE CONFIRMED BOOKING
                # ----------------------------------------

                booking_result = (
                    await session.execute(
                        text("""
                            INSERT INTO bookings (
                                user_id,
                                seat_id,
                                reservation_id
                            )
                            VALUES (
                                :user_id,
                                :seat_id,
                                :reservation_id
                            )
                            RETURNING id
                        """),
                        {
                            "user_id":
                                reservation[
                                    "user_id"
                                ],

                            "seat_id":
                                reservation[
                                    "seat_id"
                                ],

                            "reservation_id":
                                reservation_id
                        }
                    )
                )

                booking_id = (
                    booking_result
                    .scalar_one()
                )                # ----------------------------------------
                # QUEUE -> BOOKED
                # ----------------------------------------

                await session.execute(
                    text("""
                        UPDATE booking_requests
                        SET status = 'BOOKED'
                        WHERE id = (
                            SELECT id
                            FROM booking_requests
                            WHERE user_id = :user_id
                              AND status = 'ALLOCATED'
                            ORDER BY id DESC
                            LIMIT 1
                        )
                    """),
                    {
                        "user_id": reservation["user_id"]
                    }
                )

            return {
                "success": True,
                "message":
                    "Payment successful",
                "booking_id":
                    booking_id,
                "reservation_id":
                    reservation_id,
                "user_id":
                    reservation["user_id"],
                "seat":
                    reservation[
                        "seat_number"
                    ],
                "status":
                    "BOOKED"
            }

        except Exception as e:

            await session.rollback()

            return {
                "success": False,
                "error":
                    str(e)
            }


# ============================================================
# PAYMENT FAILURE
# ============================================================

@app.post(
    "/payment/{reservation_id}/failure"
)
async def payment_failure(
    reservation_id: int
):

    async with AsyncSessionLocal() as session:

        try:

            async with session.begin():

                result = await session.execute(
                    text("""
                        SELECT
                            r.id,
                            r.user_id,
                            r.seat_id,
                            r.status,
                            s.seat_number

                        FROM reservations r

                        JOIN seats s
                          ON s.id = r.seat_id

                        WHERE r.id =
                            :reservation_id

                        FOR UPDATE OF r
                    """),
                    {
                        "reservation_id":
                            reservation_id
                    }
                )

                reservation = (
                    result
                    .mappings()
                    .first()
                )

                if reservation is None:

                    return {
                        "success": False,
                        "message":
                            "Reservation not found"
                    }

                if (
                    reservation["status"]
                    != "HELD"
                ):

                    return {
                        "success": False,
                        "message":
                            "Reservation is already "
                            + reservation["status"]
                    }

                # ----------------------------------------
                # MARK PAYMENT FAILED
                # ----------------------------------------

                await session.execute(
                    text("""
                        UPDATE reservations
                        SET status = 'FAILED'
                        WHERE id =
                            :reservation_id
                          AND status = 'HELD'
                    """),
                    {
                        "reservation_id":
                            reservation_id
                    }
                )

                # ----------------------------------------
                # RELEASE SEAT
                # ----------------------------------------

                await session.execute(
                    text("""
                        UPDATE seats
                        SET status = 'AVAILABLE'
                        WHERE id = :seat_id
                          AND status = 'HELD'
                    """),
                    {
                        "seat_id":
                            reservation[
                                "seat_id"
                            ]
                    }
                )
                                # ----------------------------------------
                # QUEUE -> REJECTED
                # ----------------------------------------

                await session.execute(
                    text("""
                        UPDATE booking_requests
                        SET status = 'REJECTED'
                        WHERE id = (
                            SELECT id
                            FROM booking_requests
                            WHERE user_id = :user_id
                              AND status = 'ALLOCATED'
                            ORDER BY id DESC
                            LIMIT 1
                        )
                    """),
                    {
                        "user_id": reservation["user_id"]
                    }
                )

            return {
                "success": True,
                "message":
                    "Payment failed - seat released",
                "reservation_id":
                    reservation_id,
                "user_id":
                    reservation[
                        "user_id"
                    ],
                "seat":
                    reservation[
                        "seat_number"
                    ],
                "status":
                    "AVAILABLE"
            }

        except Exception as e:

            await session.rollback()

            return {
                "success": False,
                "error":
                    str(e)
            }


# ============================================================
# MANUAL EXPIRY
#
# Automatic expiry already runs every second.
# This remains useful as an admin/debug endpoint.
# ============================================================

@app.post("/expire")
async def expire_reservations():

    async with AsyncSessionLocal() as session:

        try:

            async with session.begin():

                result = await session.execute(
                    text("""
                        SELECT
                            id,
                            seat_id

                        FROM reservations

                        WHERE status = 'HELD'
                          AND expires_at
                              <= CURRENT_TIMESTAMP

                        FOR UPDATE SKIP LOCKED
                    """)
                )

                expired = (
                    result
                    .mappings()
                    .all()
                )

                for reservation in expired:

                    await session.execute(
                        text("""
                            UPDATE reservations
                            SET status = 'EXPIRED'
                            WHERE id =
                                :reservation_id
                              AND status = 'HELD'
                        """),
                        {
                            "reservation_id":
                                reservation["id"]
                        }
                    )

                    await session.execute(
                        text("""
                            UPDATE seats
                            SET status = 'AVAILABLE'
                            WHERE id = :seat_id
                              AND status = 'HELD'
                        """),
                        {
                            "seat_id":
                                reservation[
                                    "seat_id"
                                ]
                        }
                    )

            return {
                "success": True,
                "expired_reservations":
                    len(expired),
                "released_seats":
                    len(expired)
            }

        except Exception as e:

            await session.rollback()

            return {
                "success": False,
                "error":
                    str(e)
            }


# ============================================================
# GET QUEUE
# ============================================================

@app.get("/queue")
async def get_queue():

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            text("""
                SELECT
                    queue_number,
                    user_id,
                    status,
                    created_at

                FROM booking_requests

                ORDER BY queue_number
            """)
        )

        requests = (
            result
            .mappings()
            .all()
        )

    return {
        "total_requests":
            len(requests),

        "queue": [
            dict(item)
            for item in requests
        ]
    }


# ============================================================
# STATISTICS
# ============================================================

@app.get("/stats")
async def stats():

    async with AsyncSessionLocal() as session:

        # ----------------------------------------
        # SEAT STATISTICS
        # ----------------------------------------

        seat_result = (
            await session.execute(
                text("""
                    SELECT
                        COUNT(*) AS total,

                        COUNT(*) FILTER (
                            WHERE status =
                                'AVAILABLE'
                        ) AS available,

                        COUNT(*) FILTER (
                            WHERE status =
                                'HELD'
                        ) AS held,

                        COUNT(*) FILTER (
                            WHERE status =
                                'BOOKED'
                        ) AS booked

                    FROM seats
                """)
            )
        )

        seat_stats = (
            seat_result
            .mappings()
            .one()
        )

        # ----------------------------------------
        # RESERVATION STATISTICS
        # ----------------------------------------

        reservation_result = (
            await session.execute(
                text("""
                    SELECT

                        COUNT(*)
                            AS total_reservations,

                        COUNT(*) FILTER (
                            WHERE status =
                                'HELD'
                        )
                            AS active_reservations,

                        COUNT(*) FILTER (
                            WHERE status =
                                'BOOKED'
                        )
                            AS booked_reservations,

                        COUNT(*) FILTER (
                            WHERE status =
                                'EXPIRED'
                        )
                            AS expired_reservations,

                        COUNT(*) FILTER (
                            WHERE status =
                                'FAILED'
                        )
                            AS failed_reservations

                    FROM reservations
                """)
            )
        )

        reservation_stats = (
            reservation_result
            .mappings()
            .one()
        )

        # ----------------------------------------
        # QUEUE STATISTICS
        # ----------------------------------------

        queue_result = (
            await session.execute(
                text("""
                    SELECT

                        COUNT(*)
                            AS total_requests,

                        COUNT(*) FILTER (
                            WHERE status = 'WAITING'
                        )
                            AS waiting,

                        COUNT(*) FILTER (
                            WHERE status = 'ALLOCATED'
                        )
                            AS allocated,

                        COUNT(*) FILTER (
                            WHERE status = 'BOOKED'
                        )
                            AS booked,

                        COUNT(*) FILTER (
                            WHERE status = 'REJECTED'
                        )
                            AS rejected,

                        COUNT(*) FILTER (
                            WHERE status = 'EXPIRED'
                        )
                            AS expired,

                        COUNT(*) FILTER (
                            WHERE status = 'SOLD_OUT'
                        )
                            AS sold_out

                    FROM booking_requests
                """)
            )
        )

        queue_stats = (
            queue_result
            .mappings()
            .one()
        )

    return {
        "seats":
            dict(seat_stats),

        "reservations":
            dict(reservation_stats),

        "queue":
            dict(queue_stats)
    }
@app.post("/simulate-rush")
async def simulate_rush():
    return await run_simulation(
        users=1000,
        concurrency=200
    )