from datetime import datetime
from typing import List, Optional

import aiosqlite
from fastapi import Depends, HTTPException, status

from app.db import get_db
from app.schemas import ApartmentCreate, ApartmentUpdate


class ApartmentService:
    def __init__(self, db: aiosqlite.Connection = Depends(get_db)) -> None:
        self._db = db

    async def create_apartment(self, owner_id: int, payload: ApartmentCreate) -> int:
        cursor = await self._db.execute(
            """
            INSERT INTO apartments (owner_id, title, description, city, price, guests, is_published, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                owner_id,
                payload.title,
                payload.description,
                payload.city,
                payload.price,
                payload.guests,
                datetime.utcnow().isoformat(),
            ),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def update_apartment(self, owner_id: int, apartment_id: int, payload: ApartmentUpdate) -> None:
        apartment = await self.get_apartment_by_id(apartment_id)
        if not apartment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")
        if apartment["owner_id"] != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на редактирование")
        fields = {k: v for k, v in payload.dict().items() if v is not None}
        if not fields:
            return
        sets = ", ".join([f"{key} = ?" for key in fields.keys()])
        values = list(fields.values())
        values.append(apartment_id)
        await self._db.execute(f"UPDATE apartments SET {sets} WHERE id = ?", values)
        await self._db.commit()

    async def delete_apartment(self, owner_id: int, apartment_id: int) -> None:
        apartment = await self.get_apartment_by_id(apartment_id)
        if not apartment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")
        if apartment["owner_id"] != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на удаление")
        await self._db.execute("DELETE FROM apartments WHERE id = ?", (apartment_id,))
        await self._db.commit()

    async def set_publish(self, owner_id: int, apartment_id: int, is_published: bool) -> None:
        apartment = await self.get_apartment_by_id(apartment_id)
        if not apartment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")
        if apartment["owner_id"] != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав на изменение публикации")
        await self._db.execute(
            "UPDATE apartments SET is_published = ? WHERE id = ?",
            (1 if is_published else 0, apartment_id),
        )
        await self._db.commit()

    async def list_own(self, owner_id: int) -> List[dict]:
        cursor = await self._db.execute("SELECT * FROM apartments WHERE owner_id = ?", (owner_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def list_public(
        self,
        city: Optional[str] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
        guests: Optional[int] = None,
    ) -> List[dict]:
        filters = ["is_published = 1"]
        params: List[object] = []
        if city:
            filters.append("city LIKE ? COLLATE NOCASE")
            params.append(f"%{city.strip()}%")
        if price_from is not None:
            filters.append("price >= ?")
            params.append(price_from)
        if price_to is not None:
            filters.append("price <= ?")
            params.append(price_to)
        if guests is not None:
            filters.append("guests >= ?")
            params.append(guests)
        where_clause = " AND ".join(filters)
        cursor = await self._db.execute(f"SELECT * FROM apartments WHERE {where_clause}", params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_apartment_by_id(self, apartment_id: int) -> Optional[dict]:
        cursor = await self._db.execute("SELECT * FROM apartments WHERE id = ?", (apartment_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_public_apartment(self, apartment_id: int) -> Optional[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM apartments WHERE id = ? AND is_published = 1",
            (apartment_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
