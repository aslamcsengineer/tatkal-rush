import asyncio
from sqlalchemy import text
from database import engine


async def setup_database():
    async with engine.begin() as conn:

        # Drop existing prototype tables one at a time
        await conn.execute(text(
            "DROP TABLE IF EXISTS bookings CASCADE"
        ))

        await conn.execute(text(
            "DROP TABLE IF EXISTS reservations CASCADE"
        ))

        await conn.execute(text(
            "DROP TABLE IF EXISTS booking_requests CASCADE"
        ))

        await conn.execute(text(
            "DROP TABLE IF EXISTS seats CASCADE"
        ))

        # -----------------------------
        # SEATS
        # -----------------------------
        await conn.execute(text("""
            CREATE TABLE seats (
                id SERIAL PRIMARY KEY,
                seat_number VARCHAR(20) UNIQUE NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
                CHECK (
                    status IN ('AVAILABLE', 'HELD', 'BOOKED')
                )
            )
        """))

        # -----------------------------
        # BOOKING REQUESTS
        # -----------------------------
        await conn.execute(text("""
            CREATE TABLE booking_requests (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                queue_number BIGINT,
                status VARCHAR(20) NOT NULL DEFAULT 'WAITING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # -----------------------------
        # RESERVATIONS
        # -----------------------------
        await conn.execute(text("""
            CREATE TABLE reservations (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,

                seat_id INTEGER NOT NULL
                    REFERENCES seats(id),

                status VARCHAR(20)
                    NOT NULL
                    DEFAULT 'HELD',

                created_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                expires_at TIMESTAMP NOT NULL
            )
        """))

        # -----------------------------
        # BOOKINGS
        # -----------------------------
        await conn.execute(text("""
            CREATE TABLE bookings (
                id SERIAL PRIMARY KEY,

                user_id VARCHAR(50) NOT NULL,

                seat_id INTEGER NOT NULL
                    REFERENCES seats(id),

                reservation_id INTEGER
                    REFERENCES reservations(id),

                booked_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(seat_id)
            )
        """))

        # -----------------------------
        # CREATE 10 TATKAL SEATS
        # -----------------------------
        await conn.execute(text("""
            INSERT INTO seats (seat_number)
            SELECT
                'T' ||
                LPAD(generate_series(1, 10)::text, 2, '0')
        """))

    print("--------------------------------")
    print("Tatkal Rush Database Ready")
    print("--------------------------------")
    print("10 Tatkal seats created")
    print("Seats: T01 - T10")
    print("--------------------------------")


if __name__ == "__main__":
    asyncio.run(setup_database())