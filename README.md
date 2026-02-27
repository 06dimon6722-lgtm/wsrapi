# API сервиса аренды квартир (FastAPI)

## Установка

1. Перейдите в папку проекта:

2. Установите зависимости:

pip install -r requirements.txt

## Запуск

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

После запуска:
- Swagger: `http://<SERVER_IP>:8000/docs`
- Админка: `http://<SERVER_IP>:8000/admin`

Логин/пароль админа:
- `admin`
- `mikadzeadm`

## Важно

- В каждый запрос API добавляйте заголовок `ClientId`.
- Авторизация в API через `Authorization: Bearer <token>`.
- Фото загружаются сразу в `POST /apartments` и `PATCH /apartments/{apartment_id}` (формат `multipart/form-data`, поле `photos` можно передавать несколько раз).
- В ответах по объявлениям (`/apartments/me`, `/catalog/apartments`, `/catalog/apartments/{id}` и т.д.) фото приходят в поле `photo_urls` как URL.

