from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user
from app.models import AuthResponse, LoginRequest, SignupRequest, UserPublic, user_to_public
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest) -> AuthResponse:
    user = await auth_service.create_user(payload.full_name, payload.email, payload.password)
    token = auth_service.issue_token(user)
    return AuthResponse(access_token=token, user=user_to_public(user))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    user = await auth_service.authenticate(payload.email, payload.password)
    token = auth_service.issue_token(user)
    return AuthResponse(access_token=token, user=user_to_public(user))


@router.post("/guest", response_model=AuthResponse)
async def guest() -> AuthResponse:
    user = await auth_service.create_guest_user()
    token = auth_service.issue_token(user)
    return AuthResponse(access_token=token, user=user_to_public(user))


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)) -> UserPublic:
    return user_to_public(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(_: dict = Depends(get_current_user)) -> None:
    return None
