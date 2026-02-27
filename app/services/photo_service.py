from typing import Dict, List, Optional

import aiosqlite
from fastapi import Depends, HTTPException, status

from app.db import get_db


class PhotoService:
    def __init__(self, db: aiosqlite.Connection = Depends(get_db)) -> None:
        self._db = db

    async def add_photo_urls(self, owner_id: int, apartment_id: int, photo_urls: List[str]) -> None:
        if not photo_urls:
            return
        apartment = await self._get_apartment(apartment_id)
        if not apartment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")
        if apartment["owner_id"] != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на добавление фото")

        current_order = await self._next_sort_order(apartment_id)
        for index, url in enumerate(photo_urls):
            await self._db.execute(
                """
                INSERT INTO apartment_photos (apartment_id, url, sort_order)
                VALUES (?, ?, ?)
                """,
                (apartment_id, url, current_order + index),
            )
        await self._db.commit()

    async def list_photo_urls(self, apartment_id: int) -> List[str]:
        cursor = await self._db.execute(
            """
            SELECT url
            FROM apartment_photos
            WHERE apartment_id = ?
            ORDER BY sort_order, id
            """,
            (apartment_id,),
        )
        rows = await cursor.fetchall()
        return [row["url"] for row in rows]

    async def list_photo_urls_bulk(self, apartment_ids: List[int]) -> Dict[int, List[str]]:
        if not apartment_ids:
            return {}
        placeholders = ", ".join(["?"] * len(apartment_ids))
        cursor = await self._db.execute(
            f"""
            SELECT apartment_id, url
            FROM apartment_photos
            WHERE apartment_id IN ({placeholders})
            ORDER BY sort_order, id
            """,
            apartment_ids,
        )
        rows = await cursor.fetchall()
        photos_map: Dict[int, List[str]] = {apartment_id: [] for apartment_id in apartment_ids}
        for row in rows:
            photos_map[row["apartment_id"]].append(row["url"])
        return photos_map

    async def _next_sort_order(self, apartment_id: int) -> int:
        cursor = await self._db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM apartment_photos WHERE apartment_id = ?",
            (apartment_id,),
        )
        row = await cursor.fetchone()
        return int(row["next_order"])

    async def _get_apartment(self, apartment_id: int) -> Optional[dict]:
        cursor = await self._db.execute("SELECT * FROM apartments WHERE id = ?", (apartment_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
