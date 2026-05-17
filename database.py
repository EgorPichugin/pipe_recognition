from pathlib import Path
import os
import sqlite3


DATA_DIR = Path(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "."))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "pipe_recognition.db"))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recognition_results (
                id INTEGER PRIMARY KEY,
                image_name TEXT NOT NULL,
                image_hashvalue TEXT NOT NULL,
                category INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(recognition_results)")
        }
        if "image_name" not in columns:
            connection.execute(
                "ALTER TABLE recognition_results ADD COLUMN image_name TEXT"
            )
        if "image_hashvalue" not in columns:
            connection.execute(
                "ALTER TABLE recognition_results ADD COLUMN image_hashvalue TEXT"
            )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_recognition_results_image_name
            ON recognition_results (image_name)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_recognition_results_image_hashvalue
            ON recognition_results (image_hashvalue)
            """
        )
