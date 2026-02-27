from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


PASSWORD_SPECIALS = "_#!%"


class UserRegister(BaseModel):
    email: EmailStr = Field(..., description="Email пользователя")
    name: str = Field(..., min_length=1, description="Имя (только латиница)")
    password: str = Field(..., min_length=3, description="Пароль")

    @validator("name")
    def name_is_latin(cls, value: str) -> str:
        if not value.isascii() or not value.isalpha():
            raise ValueError("Имя: только английские буквы A-Z без пробелов и цифр")
        return value

    @validator("password")
    def password_policy(cls, value: str) -> str:
        ok = (
            len(value) >= 3
            and any(ch.islower() for ch in value)
            and any(ch.isupper() for ch in value)
            and any(ch.isdigit() for ch in value)
            and any(ch in PASSWORD_SPECIALS for ch in value)
        )
        if not ok:
            raise ValueError(
                "Пароль: минимум 3 символа, 1 заглавная, 1 строчная, 1 цифра и один спецсимвол из _#!% (пример: Qwerty1_)."
            )
        return value


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(..., description="Пароль")


class TokenOut(BaseModel):
    access_token: str = Field(..., description="JWT токен")
    token_type: str = Field("bearer", description="Тип токена")


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str


class ApartmentBase(BaseModel):
    title: str = Field(..., min_length=1, description="Заголовок")
    description: str = Field(..., min_length=1, description="Описание")
    city: str = Field(..., min_length=1, description="Город")
    price: int = Field(..., ge=1, description="Цена за сутки")
    guests: int = Field(..., ge=1, description="Количество гостей")


class ApartmentCreate(ApartmentBase):
    pass


class ApartmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, description="Заголовок")
    description: Optional[str] = Field(None, min_length=1, description="Описание")
    city: Optional[str] = Field(None, min_length=1, description="Город")
    price: Optional[int] = Field(None, ge=1, description="Цена за сутки")
    guests: Optional[int] = Field(None, ge=1, description="Количество гостей")


class ApartmentOut(ApartmentBase):
    id: int
    owner_id: int
    is_published: bool
    photo_urls: list[str] = Field(default_factory=list, description="URL фото")

class BookingCreate(BaseModel):
    date_from: date = Field(..., description="Дата заезда")
    date_to: date = Field(..., description="Дата выезда")

    @validator("date_to")
    def date_to_after_from(cls, value: date, values):
        date_from = values.get("date_from")
        if date_from and value <= date_from:
            raise ValueError("Дата выезда должна быть позже даты заезда")
        return value


class BookingOut(BaseModel):
    id: int
    apartment_id: int
    user_id: int
    date_from: date
    date_to: date
    status: str

