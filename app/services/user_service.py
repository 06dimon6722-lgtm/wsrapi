from datetime import datetime
from typing import Optional

import aiosqlite
from fastapi import Depends, HTTPException, status

from app.security import get_password_hash, verify_password
from app.db import get_db
from app.schemas import UserRegister


class UserService:
    def __init__(self, db: aiosqlite.Connection = Depends(get_db)) -> None:
        self._db = db

    async def register_user(self, payload: UserRegister) -> int:
        existing = await self.get_user_by_email(payload.email)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже зарегистрирован")
        password_hash = get_password_hash(payload.password)
        cursor = await self._db.execute(
            """
            INSERT INTO users (email, name, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (payload.email, payload.name, password_hash, datetime.utcnow().isoformat()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def authenticate(self, email: str, password: str) -> Optional[dict]:
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        cursor = await self._db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        cursor = await self._db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
