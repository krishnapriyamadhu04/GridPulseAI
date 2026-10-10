import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from backend.auth import DATABASE


def initialize_energy_storage():
    """Create the user-specific energy readings table."""

    with sqlite3.connect(DATABASE) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS energy_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reading_date TEXT NOT NULL,
                consumption_kwh REAL NOT NULL
                    CHECK (consumption_kwh >= 0),
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_energy_user_date
            ON energy_readings(user_id, reading_date)
        """)


def save_reading(
    user_id: int,
    reading_date: str,
    consumption_kwh: float,
    source: str
):
    """Save a confirmed consumption reading for one user."""

    if consumption_kwh < 0:
        raise HTTPException(
            status_code=400,
            detail="Consumption cannot be negative."
        )

    with sqlite3.connect(DATABASE) as connection:
        connection.execute("""
            INSERT INTO energy_readings (
                user_id,
                reading_date,
                consumption_kwh,
                source,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            reading_date,
            consumption_kwh,
            source,
            datetime.now(timezone.utc).isoformat()
        ))


def get_user_readings(user_id: int):
    """Return readings belonging only to the signed-in user."""

    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT
                id,
                reading_date,
                consumption_kwh,
                source
            FROM energy_readings
            WHERE user_id = ?
            ORDER BY reading_date
        """, (user_id,)).fetchall()

    return [dict(row) for row in rows]