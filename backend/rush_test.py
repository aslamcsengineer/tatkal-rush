import asyncio
import time
from collections import Counter

import httpx


API_URL = "http://127.0.0.1:8000"

DEFAULT_USERS = 1000
DEFAULT_CONCURRENCY = 200


async def run_rush_test(
    users: int = DEFAULT_USERS,
    concurrency: int = DEFAULT_CONCURRENCY,
):
    """
    Sends many concurrent booking requests to the real FastAPI /book
    endpoint and returns concurrency-test statistics.
    """

    semaphore = asyncio.Semaphore(concurrency)

    async def send_booking(client, user_number):
        async with semaphore:
            try:
                response = await client.post(
                    f"{API_URL}/book",
                    json={
                        "user_id": f"RUSH-{user_number:04d}"
                    },
                    timeout=60.0,
                )

                return {
                    "http_status": response.status_code,
                    "data": response.json(),
                }

            except Exception as error:
                return {
                    "http_status": 0,
                    "data": {
                        "success": False,
                        "message": str(error),
                    },
                }

    started = time.perf_counter()

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )

    timeout = httpx.Timeout(60.0)

    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
    ) as client:

        tasks = [
            send_booking(client, number)
            for number in range(1, users + 1)
        ]

        results = await asyncio.gather(*tasks)

    execution_time = time.perf_counter() - started

    # ---------------------------------------------------------
    # ANALYSE RESULTS
    # ---------------------------------------------------------

    successful = []
    rejected = []
    errors = []

    queue_numbers = []

    for result in results:
        data = result["data"]

        queue_number = data.get("queue_number")

        if queue_number is not None:
            queue_numbers.append(queue_number)

        if data.get("success") is True:
            successful.append(data)

        else:
            rejected.append(data)

            if result["http_status"] == 0:
                errors.append(data)

    allocated_seats = [
        result.get("seat")
        for result in successful
        if result.get("seat")
    ]

    seat_counts = Counter(allocated_seats)

    duplicate_seats = {
        seat: count
        for seat, count in seat_counts.items()
        if count > 1
    }

    unique_seats = len(set(allocated_seats))

    duplicate_queue_ids = (
        len(queue_numbers)
        - len(set(queue_numbers))
    )

    # ---------------------------------------------------------
    # CONSISTENCY RESULT
    # ---------------------------------------------------------

    consistency_pass = (
        len(duplicate_seats) == 0
        and duplicate_queue_ids == 0
    )

    return {
        "success": True,

        "configuration": {
            "artificial_users": users,
            "concurrency": concurrency,
        },

        "results": {
            "total_requests": len(results),

            "successful_holds": len(successful),

            "rejected_requests": len(rejected),

            "unique_seats_allocated": unique_seats,

            "duplicate_seat_allocations":
                len(duplicate_seats),

            "queue_ids_issued":
                len(queue_numbers),

            "duplicate_queue_ids":
                duplicate_queue_ids,

            "request_errors":
                len(errors),

            "execution_time_seconds":
                round(execution_time, 2),
        },

        "allocated_seats":
            allocated_seats,

        "winning_queue_numbers": [
            result.get("queue_number")
            for result in successful
        ],

        "duplicate_details":
            duplicate_seats,

        "verification": {
            "consistency":
                "PASS"
                if consistency_pass
                else "FAIL",

            "zero_double_booking":
                len(duplicate_seats) == 0,

            "unique_queue_ids":
                duplicate_queue_ids == 0,
        },
    }


# Allows us to test this file directly.
if __name__ == "__main__":

    async def main():
        result = await run_rush_test()

        print("\n" + "=" * 60)
        print("TATKAL RUSH LIVE SIMULATION")
        print("=" * 60)

        print(
            "Artificial users :",
            result["configuration"]["artificial_users"],
        )

        print(
            "Concurrency      :",
            result["configuration"]["concurrency"],
        )

        print("-" * 60)

        results = result["results"]

        print(
            "Total requests   :",
            results["total_requests"],
        )

        print(
            "Successful holds :",
            results["successful_holds"],
        )

        print(
            "Rejected         :",
            results["rejected_requests"],
        )

        print(
            "Unique seats     :",
            results["unique_seats_allocated"],
        )

        print(
            "Duplicate seats  :",
            results["duplicate_seat_allocations"],
        )

        print(
            "Queue IDs        :",
            results["queue_ids_issued"],
        )

        print(
            "Duplicate queues :",
            results["duplicate_queue_ids"],
        )

        print(
            "Execution time   :",
            results["execution_time_seconds"],
            "seconds",
        )

        print("-" * 60)

        verification = result["verification"]

        print(
            "CONSISTENCY      :",
            verification["consistency"],
        )

        print(
            "ZERO DOUBLE BOOK :",
            verification["zero_double_booking"],
        )

        print(
            "UNIQUE QUEUE IDs :",
            verification["unique_queue_ids"],
        )

        print("=" * 60)

    asyncio.run(main())