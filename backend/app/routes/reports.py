import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.config import REPORTS_DIR
from app.deps import get_current_user
from app.models import AnalysisResponse, ReportSummary
from app.services import report_service
from app.services.pdf_service import build_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportSummary])
async def list_reports(current_user: dict = Depends(get_current_user)) -> list[ReportSummary]:
    reports = await report_service.list_reports(current_user["_id"])
    return [
        ReportSummary(
            id=str(r["_id"]),
            title=r.get("title", "Bowling Analysis"),
            created_at=r.get("created_at"),
            overall_score=r.get("overall_score", 0.0),
            efficiency_score=r.get("efficiency_score", 0.0),
        )
        for r in reports
    ]


@router.get("/{report_id}", response_model=AnalysisResponse)
async def get_report(report_id: str, current_user: dict = Depends(get_current_user)) -> AnalysisResponse:
    report = await report_service.get_report(report_id, current_user["_id"])
    return AnalysisResponse(**report_service.to_response(report))


@router.get("/{report_id}/pdf")
async def download_pdf(report_id: str, current_user: dict = Depends(get_current_user)):
    report = await report_service.get_report(report_id, current_user["_id"])
    pdf_path_str = report.get("pdf_report_path")
    pdf_path = Path(pdf_path_str) if pdf_path_str else REPORTS_DIR / f"report-{report['_id']}.pdf"
    if not pdf_path.exists():
        try:
            await asyncio.to_thread(
                build_pdf, pdf_path, current_user.get("full_name", "Athlete"), report_service.to_response(report)
            )
            await report_service.set_pdf_path(report["_id"], str(pdf_path))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)
