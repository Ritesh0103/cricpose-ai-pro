from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import DashboardSummary, UserPublic, user_to_public
from app.services import report_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)) -> UserPublic:
    return user_to_public(current_user)


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(current_user: dict = Depends(get_current_user)) -> DashboardSummary:
    data = await report_service.dashboard_summary(current_user["_id"])
    return DashboardSummary(**data)
