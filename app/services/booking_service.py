from datetime import datetime
from typing import List, Optional

import aiosqlite
from fastapi import Depends, HTTPException, status

from app.db import get_db
from app.schemas import BookingCreate


class BookingService:
    def __init__(self, db: aiosqlite.Connection = Depends(get_db)) -> None:
        self._db = db

    async def create_booking(self, user_id: int, apartment_id: int, payload: BookingCreate) -> int:
        apartment = await self._get_apartment(apartment_id)
        if not apartment or apartment["is_published"] != 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")

        date_from = payload.date_from.isoformat()
        date_to = payload.date_to.isoformat()
        if not await self._is_available(apartment_id, date_from, date_to):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Даты недоступны")

        cursor = await self._db.execute(
            """
            INSERT INTO bookings (apartment_id, user_id, date_from, date_to, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                apartment_id,
                user_id,
                date_from,
                date_to,
                "active",
                datetime.utcnow().isoformat(),
            ),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_own(self, user_id: int) -> List[dict]:
        cursor = await self._db.execute("SELECT * FROM bookings WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_booking(self, booking_id: int) -> Optional[dict]:
        return await self._get_booking(booking_id)

    async def cancel_booking(self, user_id: int, booking_id: int) -> None:
        booking = await self._get_booking(booking_id)
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено")
        if booking["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на отмену")
        if booking["status"] != "active":
            return
        await self._db.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            ("cancelled", booking_id),
        )
        await self._db.commit()

    async def _is_available(self, apartment_id: int, date_from: str, date_to: str) -> bool:
        cursor = await self._db.execute(
            """
            SELECT COUNT(1) AS cnt
            FROM bookings
            WHERE apartment_id = ?
              AND status = 'active'
              AND NOT (date_to <= ? OR date_from >= ?)
            """,
            (apartment_id, date_from, date_to),
        )
        row = await cursor.fetchone()
        return row["cnt"] == 0

    async def _get_apartment(self, apartment_id: int):
        cursor = await self._db.execute("SELECT * FROM apartments WHERE id = ?", (apartment_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def _get_booking(self, booking_id: int):
        cursor = await self._db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
