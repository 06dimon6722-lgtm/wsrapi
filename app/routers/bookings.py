from fastapi import APIRouter, Depends, status

from app.auth import get_current_user
from app.deps import require_client_id
from app.schemas import BookingCreate, BookingOut
from app.services.booking_service import BookingService


router = APIRouter(
    prefix="/bookings",
    tags=["Бронирования"],
    dependencies=[Depends(require_client_id)],
)


@router.post(
    "/{apartment_id}",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Забронировать квартиру",
    description="Создать бронирование на выбранные даты.",
)
async def create_booking(
    apartment_id: int,
    payload: BookingCreate,
    user=Depends(get_current_user),
    service: BookingService = Depends(BookingService),
):
    booking_id = await service.create_booking(user["id"], apartment_id, payload)
    booking = await service.get_booking(booking_id)
    return _map_booking(booking)


@router.get(
    "/me",
    response_model=list[BookingOut],
    summary="Мои бронирования",
    description="Получить список своих бронирований.",
)
async def list_own(user=Depends(get_current_user), service: BookingService = Depends(BookingService)):
    bookings = await service.list_own(user["id"])
    return [_map_booking(b) for b in bookings]


@router.post(
    "/{booking_id}/cancel",
    summary="Отменить бронирование",
    description="Отменить свое бронирование, если это разрешено правилами API.",
)
async def cancel_booking(
    booking_id: int,
    user=Depends(get_current_user),
    service: BookingService = Depends(BookingService),
):
    await service.cancel_booking(user["id"], booking_id)
    return {"status": "cancelled"}


def _map_booking(row: dict) -> BookingOut:
    return {
        "id": row["id"],
        "apartment_id": row["apartment_id"],
        "user_id": row["user_id"],
        "date_from": row["date_from"],
        "date_to": row["date_to"],
        "status": row["status"],
    }
