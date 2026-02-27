import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.auth import get_current_user
from app.db import DATA_DIR
from app.deps import require_client_id
from app.schemas import ApartmentCreate, ApartmentOut, ApartmentUpdate
from app.services.apartment_service import ApartmentService
from app.services.photo_service import PhotoService


UPLOADS_ROOT = Path(DATA_DIR) / "uploads"
EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

router = APIRouter(
    prefix="/apartments",
    tags=["Квартиры (личные)"],
    dependencies=[Depends(require_client_id)],
)


@router.post(
    "",
    response_model=ApartmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать объявление",
    description="Создать объявление о сдаче квартиры вместе с фото. Объявление создается как непубличное.",
)
async def create_apartment(
    request: Request,
    title: str = Form(..., min_length=1, description="Заголовок"),
    description: str = Form(..., min_length=1, description="Описание"),
    city: str = Form(..., min_length=1, description="Город"),
    price: int = Form(..., ge=1, description="Цена за сутки"),
    guests: int = Form(..., ge=1, description="Количество гостей"),
    photos: UploadFile | list[UploadFile] | None = File(None, description="Фотографии квартиры"),
    client_id: str = Depends(require_client_id),
    user=Depends(get_current_user),
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    payload = ApartmentCreate(title=title, description=description, city=city, price=price, guests=guests)
    apartment_id = await service.create_apartment(user["id"], payload)
    uploaded_urls = await _save_photos(client_id, _normalize_photos(photos))
    await photo_service.add_photo_urls(user["id"], apartment_id, uploaded_urls)

    apartment = await service.get_apartment_by_id(apartment_id)
    photo_urls = await photo_service.list_photo_urls(apartment_id)
    return _map_apartment(apartment, photo_urls, request)


@router.get(
    "/me",
    response_model=list[ApartmentOut],
    summary="Мои объявления",
    description="Получить список своих объявлений.",
)
async def list_own(
    request: Request,
    user=Depends(get_current_user),
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    apartments = await service.list_own(user["id"])
    photos_map = await photo_service.list_photo_urls_bulk([a["id"] for a in apartments])
    return [_map_apartment(a, photos_map.get(a["id"], []), request) for a in apartments]


@router.patch(
    "/{apartment_id}",
    response_model=ApartmentOut,
    summary="Редактировать объявление",
    description="Редактировать свои объявления и добавлять новые фото.",
)
async def update_apartment(
    request: Request,
    apartment_id: int,
    title: str | None = Form(None, min_length=1, description="Заголовок"),
    description: str | None = Form(None, min_length=1, description="Описание"),
    city: str | None = Form(None, min_length=1, description="Город"),
    price: int | None = Form(None, ge=1, description="Цена за сутки"),
    guests: int | None = Form(None, ge=1, description="Количество гостей"),
    photos: UploadFile | list[UploadFile] | None = File(None, description="Новые фотографии квартиры"),
    client_id: str = Depends(require_client_id),
    user=Depends(get_current_user),
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    payload = ApartmentUpdate(title=title, description=description, city=city, price=price, guests=guests)
    await service.update_apartment(user["id"], apartment_id, payload)
    uploaded_urls = await _save_photos(client_id, _normalize_photos(photos))
    await photo_service.add_photo_urls(user["id"], apartment_id, uploaded_urls)

    apartment = await service.get_apartment_by_id(apartment_id)
    if not apartment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")
    photo_urls = await photo_service.list_photo_urls(apartment_id)
    return _map_apartment(apartment, photo_urls, request)


@router.delete(
    "/{apartment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить объявление",
    description="Удалить только свои объявления.",
)
async def delete_apartment(
    apartment_id: int,
    user=Depends(get_current_user),
    service: ApartmentService = Depends(ApartmentService),
):
    await service.delete_apartment(user["id"], apartment_id)
    return None


@router.post(
    "/{apartment_id}/publish",
    response_model=ApartmentOut,
    summary="Опубликовать объявление",
    description="Сделать объявление публичным в каталоге.",
)
async def publish(
    request: Request,
    apartment_id: int,
    user=Depends(get_current_user),
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    await service.set_publish(user["id"], apartment_id, True)
    apartment = await service.get_apartment_by_id(apartment_id)
    photo_urls = await photo_service.list_photo_urls(apartment_id)
    return _map_apartment(apartment, photo_urls, request)


@router.post(
    "/{apartment_id}/unpublish",
    response_model=ApartmentOut,
    summary="Снять с публикации",
    description="Сделать объявление непубличным.",
)
async def unpublish(
    request: Request,
    apartment_id: int,
    user=Depends(get_current_user),
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    await service.set_publish(user["id"], apartment_id, False)
    apartment = await service.get_apartment_by_id(apartment_id)
    photo_urls = await photo_service.list_photo_urls(apartment_id)
    return _map_apartment(apartment, photo_urls, request)


def _map_apartment(row: dict, photo_urls: list[str], request: Request) -> ApartmentOut:
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "title": row["title"],
        "description": row["description"],
        "city": row["city"],
        "price": row["price"],
        "guests": row["guests"],
        "is_published": bool(row["is_published"]),
        "photo_urls": _to_absolute_urls(photo_urls, request),
    }


def _to_absolute_urls(photo_urls: list[str], request: Request) -> list[str]:
    base_url = str(request.base_url).rstrip("/")
    return [url if url.startswith("http://") or url.startswith("https://") else f"{base_url}{url}" for url in photo_urls]


def _safe_client_id(client_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", client_id.strip())
    return safe or "client"


async def _save_photos(client_id: str, photos: list[UploadFile]) -> list[str]:
    if not photos:
        return []

    safe_client = _safe_client_id(client_id)
    upload_dir = UPLOADS_ROOT / safe_client
    upload_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for file in photos:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно изображение")

        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")

        ext = EXT_BY_CONTENT_TYPE.get(file.content_type, Path(file.filename or "").suffix.lower())
        if not ext:
            ext = ".img"

        filename = f"{uuid4().hex}{ext}"
        file_path = upload_dir / filename
        file_path.write_bytes(data)
        urls.append(f"/uploads/{safe_client}/{filename}")

    return urls


def _normalize_photos(photos: UploadFile | list[UploadFile] | None) -> list[UploadFile]:
    if photos is None:
        return []
    if isinstance(photos, list):
        return photos
    return [photos]
