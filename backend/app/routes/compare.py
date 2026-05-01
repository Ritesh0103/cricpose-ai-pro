from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import CompareRequest, CompareResponse, CompareTargetProfile
from app.services import comparison_service, report_service

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("/profiles", response_model=list[CompareTargetProfile])
async def list_profiles(_: dict = Depends(get_current_user)) -> list[CompareTargetProfile]:
    return comparison_service.list_profiles()


@router.post("", response_model=CompareResponse)
async def compare(payload: CompareRequest, current_user: dict = Depends(get_current_user)) -> CompareResponse:
    report = await report_service.get_report(payload.analysis_id, current_user["_id"])
    return comparison_service.compare_analysis(
        report=report,
        target_bowler=payload.target_bowler,
        comparison_group=payload.comparison_group,
    )
