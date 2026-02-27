from fastapi import APIRouter, Depends, status
from fastapi import HTTPException

from app.security import create_access_token
from app.deps import require_client_id
from app.schemas import TokenOut, UserLogin, UserOut, UserRegister
from app.services.user_service import UserService


router = APIRouter(prefix="/auth", tags=["Авторизация"], dependencies=[Depends(require_client_id)])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация",
    description="Создать аккаунт. После регистрации пользователь должен перейти на страницу входа.",
)
async def register(payload: UserRegister, user_service: UserService = Depends(UserService)):
    user_id = await user_service.register_user(payload)
    user = await user_service.get_user_by_id(user_id)
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Вход",
    description="Авторизация по email и паролю. Возвращает токен доступа.",
)
async def login(payload: UserLogin, user_service: UserService = Depends(UserService)):
    user = await user_service.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    token = create_access_token(str(user["id"]))
    return {"access_token": token, "token_type": "bearer"}
