from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import os

from app.db import DATA_DIR
from app.routers import admin, apartments, auth, bookings, catalog


description = """
API для сервиса посуточной аренды квартир.

Все запросы должны содержать заголовок `ClientId` со значением вашего логина.
Авторизация выполняется с помощью токена в заголовке `Authorization: Bearer <token>`.
"""

tags_metadata = [
    {"name": "Авторизация", "description": "Регистрация и вход."},
    {"name": "Квартиры (личные)", "description": "Управление объявлениями пользователя."},
    {"name": "Каталог", "description": "Публичный каталог квартир."},
    {"name": "Бронирования", "description": "Создание и управление бронированиями."},
]



app = FastAPI(
    title="Сервис аренды квартир",
    description=description,
    version="1.0.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=os.path.join(DATA_DIR, "uploads"), check_dir=False), name="uploads")


def _clean_message(message: str) -> str:
    if message.startswith("Value error, "):
        return message.replace("Value error, ", "", 1)
    return message


def _format_loc(loc: tuple) -> str:
    skip = {"body", "query", "path", "header"}
    parts = [str(item) for item in loc if item not in skip]
    return ".".join(parts) if parts else "данные"


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = _format_loc(tuple(err.get("loc", ())))
        message = _clean_message(err.get("msg", "Некорректное значение"))
        errors.append(f"Поле {field}: {message}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "Ошибка проверки данных",
            "errors": errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": status.HTTP_500_INTERNAL_SERVER_ERROR, "message": "Ошибка сервера. Попробуйте позже."},
    )


@app.on_event("startup")
async def startup() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


app.include_router(auth.router)
app.include_router(apartments.router)
app.include_router(catalog.router)
app.include_router(bookings.router)
app.include_router(admin.router, include_in_schema=False)
