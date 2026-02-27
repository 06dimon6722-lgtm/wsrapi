from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.deps import require_client_id
from app.services.photo_service import PhotoService


router = APIRouter(
    prefix="/photos",
    tags=["Фото"],
    dependencies=[Depends(require_client_id)],
)


@router.get(
    "/{photo_id}",
    summary="Получить фото",
    description="Вернуть фото по идентификатору.",
    responses={200: {"content": {"image/*": {}}}},
)
async def get_photo(photo_id: int, photo_service: PhotoService = Depends(PhotoService)):
    photo = await photo_service.get_photo(photo_id)
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено")
    return Response(content=photo["data"], media_type=photo["content_type"])
