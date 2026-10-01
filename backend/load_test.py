import asyncio
import time
from collections import Counter

import httpx


URL = "http://127.0.0.1:8000/book"

TOTAL_USERS = 1000

# Higher concurrency so test completes quickly
CONCURRENCY = 200


async def book_user(
    client,
    user_number,
    semaphore
):

    user_id = f"USER-{user_number:04d}"

    async with semaphore:

        try:

            response = await client.post(
                URL,
                json={
                    "user_id": user_id
                },
                timeout=20.0
            )

            return response.json()

        except Exception as e:

            return {
                "success": False,
                "user_id": user_id,
                "error": str(e)
            }


async def main():

    print("=" * 65)
    print("        TATKAL RUSH CONCURRENCY SAFETY TEST")
    print("=" * 65)

    print(
        f"Requests            : {TOTAL_USERS}"
    )

    print(
        f"Concurrency         : {CONCURRENCY}"
    )

    print(
        "Physical seats      : 10"
    )

    semaphore = asyncio.Semaphore(
        CONCURRENCY
    )

    limits = httpx.Limits(
        max_connections=CONCURRENCY,
        max_keepalive_connections=CONCURRENCY
    )

    start = time.perf_counter()

    async with httpx.AsyncClient(
        limits=limits,
        timeout=20.0
    ) as client:

        tasks = [

            book_user(
                client,
                i,
                semaphore
            )

            for i in range(
                1,
                TOTAL_USERS + 1
            )
        ]

        results = await asyncio.gather(
            *tasks
        )

    elapsed = (
        time.perf_counter()
        - start
    )

    successful = [

        r
        for r in results

        if r.get("success") is True
    ]

    failed = [

        r
        for r in results

        if r.get("success") is not True
    ]

    seats = [

        r["seat"]

        for r in successful

        if "seat" in r
    ]

    seat_counts = Counter(seats)

    duplicate_allocations = {

        seat: count

        for seat, count
        in seat_counts.items()

        if count > 1
    }

    queue_numbers = [

        r["queue_number"]

        for r in results

        if r.get("queue_number")
        is not None
    ]

    duplicate_queue_numbers = (

        len(queue_numbers)

        - len(set(queue_numbers))
    )

    print()

    print("=" * 65)
    print("                       RESULTS")
    print("=" * 65)

    print(
        f"Total responses      : "
        f"{len(results)}"
    )

    print(
        f"Successful holds     : "
        f"{len(successful)}"
    )

    print(
        f"Rejected / sold out  : "
        f"{len(failed)}"
    )

    print(
        f"Unique seats held    : "
        f"{len(set(seats))}"
    )

    print(
        f"Duplicate allocations: "
        f"{len(duplicate_allocations)}"
    )

    print(
        f"Queue IDs issued     : "
        f"{len(queue_numbers)}"
    )

    print(
        f"Duplicate queue IDs  : "
        f"{duplicate_queue_numbers}"
    )

    print(
        f"Execution time       : "
        f"{elapsed:.2f} seconds"
    )

    print()

    print(
        "Seats allocated:"
    )

    print(
        sorted(seats)
    )

    print()

    if successful:

        winning_queue_numbers = sorted(

            r["queue_number"]

            for r in successful
        )

        print(
            "Winning queue numbers:"
        )

        print(
            winning_queue_numbers
        )

    print()
    print("=" * 65)

    safety_pass = (

        len(successful) == 10

        and len(set(seats)) == 10

        and len(
            duplicate_allocations
        ) == 0
    )

    queue_pass = (

        len(queue_numbers)
        == TOTAL_USERS

        and duplicate_queue_numbers == 0
    )

    if safety_pass:

        print(
            "CONSISTENCY TEST : PASS"
        )

        print(
            "Exactly 10 active seat holds."
        )

        print(
            "ZERO DOUBLE BOOKING."
        )

    else:

        print(
            "CONSISTENCY TEST : CHECK REQUIRED"
        )

    if queue_pass:

        print(
            "QUEUE-ID TEST    : PASS"
        )

        print(
            "Every request received "
            "a unique queue ID."
        )

    else:

        print(
            "QUEUE-ID TEST    : CHECK REQUIRED"
        )

    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())