from __future__ import annotations

from typing import Any, Dict, List

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

import aiosqlite
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import DATA_DIR, database, init_db
from app.security import SECRET_KEY


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "mikadzeadm"
ADMIN_COOKIE = "admin_auth"

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/admin", tags=["Админка"])


def _admin_cookie_value() -> str:
    data = f"{ADMIN_USERNAME}:{ADMIN_PASSWORD}".encode("utf-8")
    return hashlib.sha256(SECRET_KEY.encode("utf-8") + data).hexdigest()


def _check_admin_cookie(cookie: str | None) -> bool:
    if not cookie:
        return False
    expected = _admin_cookie_value()
    return secrets.compare_digest(cookie, expected)


async def _require_admin(admin_auth: str | None = Cookie(None, alias=ADMIN_COOKIE)) -> None:
    if not _check_admin_cookie(admin_auth):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})


async def _open_db(client_id: str) -> aiosqlite.Connection:
    db_path = database.get_db_path(client_id)
    db = await database.connect(db_path)
    await init_db(None, db)
    return db


def _list_clients() -> List[str]:
    if not os.path.isdir(DATA_DIR):
        return []
    clients = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".db"):
            clients.append(filename[: -len(".db")])
    return sorted(clients)


def _table_columns(table: str) -> List[str]:
    if table == "users":
        return ["id", "email", "name", "password_hash", "created_at"]
    if table == "apartments":
        return [
            "id",
            "owner_id",
            "title",
            "description",
            "city",
            "price",
            "guests",
            "is_published",
            "created_at",
        ]
    if table == "bookings":
        return ["id", "apartment_id", "user_id", "date_from", "date_to", "status", "created_at"]
    if table == "apartment_media":
        return ["id", "apartment_id", "content_type", "data", "created_at"]
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Неизвестная таблица")


def _editable_columns(table: str) -> List[str]:
    if table == "users":
        return ["email", "name"]
    if table == "apartments":
        return ["title", "description", "city", "price", "guests", "is_published"]
    if table == "bookings":
        return ["date_from", "date_to", "status"]
    return []


def _to_msk(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if ZoneInfo is not None:
        try:
            msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
            return msk.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    msk = dt.astimezone(timezone(timedelta(hours=3)))
    return msk.strftime("%Y-%m-%d %H:%M:%S")


@router.get("/login")
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})


@router.post("/login")
async def admin_login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user_ok = secrets.compare_digest(username, ADMIN_USERNAME)
    pass_ok = secrets.compare_digest(password, ADMIN_PASSWORD)
    if not (user_ok and pass_ok):
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "Неверный логин или пароль"},
        )
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(ADMIN_COOKIE, _admin_cookie_value(), httponly=True, samesite="lax", path="/admin")
    return response


@router.get("/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(ADMIN_COOKIE, path="/admin")
    return response


@router.get("", dependencies=[Depends(_require_admin)])
@router.get("/", dependencies=[Depends(_require_admin)])
async def admin_index(request: Request):
    clients = _list_clients()
    return templates.TemplateResponse(
        "admin_index.html",
        {"request": request, "clients": clients},
    )


@router.get("/{client_id}", dependencies=[Depends(_require_admin)])
async def admin_tables(request: Request, client_id: str):
    tables = ["users", "apartments", "bookings", "apartment_media"]
    return templates.TemplateResponse(
        "admin_tables.html",
        {"request": request, "client_id": client_id, "tables": tables},
    )


@router.get("/{client_id}/table/{table}", dependencies=[Depends(_require_admin)])
async def admin_table(request: Request, client_id: str, table: str):
    columns = _table_columns(table)
    db = await _open_db(client_id)
    try:
        cursor = await db.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id DESC LIMIT 200")
        rows = await cursor.fetchall()
        rows_data = []
        for row in rows:
            row_data = dict(row)
            if "created_at" in row_data and isinstance(row_data["created_at"], str):
                row_data["created_at"] = _to_msk(row_data["created_at"])
            rows_data.append(row_data)
    finally:
        await db.close()
    return templates.TemplateResponse(
        "admin_table.html",
        {
            "request": request,
            "client_id": client_id,
            "table": table,
            "columns": columns,
            "rows": rows_data,
        },
    )


@router.get("/{client_id}/table/{table}/edit/{row_id}", dependencies=[Depends(_require_admin)])
async def admin_edit(request: Request, client_id: str, table: str, row_id: int):
    columns = _table_columns(table)
    editable = _editable_columns(table)
    if not editable:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Эту таблицу нельзя редактировать")
    db = await _open_db(client_id)
    try:
        cursor = await db.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE id = ?",
            (row_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
        row_data = dict(row)
    finally:
        await db.close()
    return templates.TemplateResponse(
        "admin_edit.html",
        {
            "request": request,
            "client_id": client_id,
            "table": table,
            "row_id": row_id,
            "editable": editable,
            "row": row_data,
        },
    )


@router.post("/{client_id}/table/{table}/edit/{row_id}", dependencies=[Depends(_require_admin)])
async def admin_edit_save(
    request: Request,
    client_id: str,
    table: str,
    row_id: int,
    email: str | None = Form(None),
    name: str | None = Form(None),
    title: str | None = Form(None),
    description: str | None = Form(None),
    city: str | None = Form(None),
    price: int | None = Form(None),
    guests: int | None = Form(None),
    is_published: int | None = Form(None),
    date_from: str | None = Form(None),
    date_to: str | None = Form(None),
    status_value: str | None = Form(None, alias="status"),
):
    editable = _editable_columns(table)
    if not editable:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Эту таблицу нельзя редактировать")

    fields: Dict[str, Any] = {}
    for key, value in {
        "email": email,
        "name": name,
        "title": title,
        "description": description,
        "city": city,
        "price": price,
        "guests": guests,
        "is_published": is_published,
        "date_from": date_from,
        "date_to": date_to,
        "status": status_value,
    }.items():
        if key in editable and value is not None:
            fields[key] = value

    if not fields:
        return Response(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": f"/admin/{client_id}/table/{table}"})

    sets = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = list(fields.values())
    values.append(row_id)
    db = await _open_db(client_id)
    try:
        await db.execute(f"UPDATE {table} SET {sets} WHERE id = ?", values)
        await db.commit()
    finally:
        await db.close()
    return Response(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": f"/admin/{client_id}/table/{table}"})


@router.get("/{client_id}/photo/{photo_id}", dependencies=[Depends(_require_admin)])
async def admin_photo(client_id: str, photo_id: int):
    db = await _open_db(client_id)
    try:
        cursor = await db.execute(
            "SELECT content_type, data FROM apartment_media WHERE id = ?",
            (photo_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено")
    finally:
        await db.close()
    return Response(content=row["data"], media_type=row["content_type"])
