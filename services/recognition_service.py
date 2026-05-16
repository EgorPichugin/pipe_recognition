import sqlite3

from database import DB_PATH
from models.responses import RecognitionResponse


def get_recognition_by_image_name(image_name: str) -> RecognitionResponse | None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, image_name, category, latitude, longitude, confidence
            FROM recognition_results
            WHERE image_name = ?
            """,
            (image_name,),
        ).fetchone()

    if row is None:
        return None

    return RecognitionResponse(
        id=row["id"],
        image_name=row["image_name"],
        category=row["category"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        confidence=row["confidence"],
        status="duplicate_name",
    )


def get_recognition_by_image_hashvalue(
    image_hashvalue: str,
) -> RecognitionResponse | None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, image_name, category, latitude, longitude, confidence
            FROM recognition_results
            WHERE image_hashvalue = ?
            """,
            (image_hashvalue,),
        ).fetchone()

    if row is None:
        return None

    return RecognitionResponse(
        id=row["id"],
        image_name=row["image_name"],
        category=row["category"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        confidence=row["confidence"],
        status="duplicate_image",
    )


def get_all_recognitions() -> list[RecognitionResponse]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, image_name, category, latitude, longitude, confidence
            FROM recognition_results
            ORDER BY id
            """
        ).fetchall()

    return [
        RecognitionResponse(
            id=row["id"],
            image_name=row["image_name"],
            category=row["category"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            confidence=row["confidence"],
            status="duplicate_name",
        )
        for row in rows
    ]


def save_recognition_result(
    image_name: str,
    image_hashvalue: str,
    result: RecognitionResponse,
) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO recognition_results (
                id,
                image_name,
                image_hashvalue,
                category,
                latitude,
                longitude,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.id,
                image_name,
                image_hashvalue,
                result.category,
                result.latitude,
                result.longitude,
                result.confidence,
            ),
        )


def delete_all_recognitions() -> int:
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute("DELETE FROM recognition_results")
        return cursor.rowcount
