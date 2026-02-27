from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.deps import require_client_id
from app.schemas import ApartmentOut
from app.services.apartment_service import ApartmentService
from app.services.photo_service import PhotoService


router = APIRouter(
    prefix="/catalog",
    tags=["Каталог"],
    dependencies=[Depends(require_client_id)],
)


@router.get(
    "/apartments",
    response_model=list[ApartmentOut],
    summary="Список публичных квартир",
    description="Получить список опубликованных квартир с фильтрами.",
)
async def list_public(
    request: Request,
    city: Optional[str] = Query(None, description="Город"),
    price_from: Optional[int] = Query(None, ge=1, description="Цена от"),
    price_to: Optional[int] = Query(None, ge=1, description="Цена до"),
    guests: Optional[int] = Query(None, ge=1, description="Минимум гостей"),
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    apartments = await service.list_public(city=city, price_from=price_from, price_to=price_to, guests=guests)
    photos_map = await photo_service.list_photo_urls_bulk([a["id"] for a in apartments])
    return [_map_apartment(a, photos_map.get(a["id"], []), request) for a in apartments]


@router.get(
    "/apartments/{apartment_id}",
    response_model=ApartmentOut,
    summary="Детальная страница квартиры",
    description="Получить детальную информацию по опубликованной квартире.",
)
async def get_public(
    request: Request,
    apartment_id: int,
    service: ApartmentService = Depends(ApartmentService),
    photo_service: PhotoService = Depends(PhotoService),
):
    apartment = await service.get_public_apartment(apartment_id)
    if not apartment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Квартира не найдена")
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
