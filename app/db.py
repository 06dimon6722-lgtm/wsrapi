import os
import re

import aiosqlite
from fastapi import FastAPI
from fastapi import Depends

from app.deps import require_client_id


DATA_DIR = "data"
DEFAULT_DB = "app.db"


class Database:
    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self._data_dir = data_dir

    def _safe_client_id(self, client_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", client_id.strip())
        return safe or "client"

    def get_db_path(self, client_id: str) -> str:
        os.makedirs(self._data_dir, exist_ok=True)
        safe_id = self._safe_client_id(client_id)
        return os.path.join(self._data_dir, f"{safe_id}.db")

    async def connect(self, db_path: str) -> aiosqlite.Connection:
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        return db


async def init_db(app: FastAPI | None, db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS apartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            city TEXT NOT NULL,
            price INTEGER NOT NULL,
            guests INTEGER NOT NULL,
            is_published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS apartment_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(apartment_id) REFERENCES apartments(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS apartment_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            data BLOB NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(apartment_id) REFERENCES apartments(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date_from TEXT NOT NULL,
            date_to TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(apartment_id) REFERENCES apartments(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    await db.commit()
    if app is not None:
        app.state.db_initialized = True


database = Database()


async def get_db(client_id: str = Depends(require_client_id)) -> aiosqlite.Connection:
    db_path = database.get_db_path(client_id)
    db = await database.connect(db_path)
    try:
        await init_db(None, db)
        yield db
    finally:
        await db.close()
