import asyncio
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.config import ALLOWED_CONTENT_TYPES, PROCESSED_DIR, REPORTS_DIR, UPLOAD_DIR
from app.deps import get_current_user
from app.models import AnalysisResponse
from app.services import report_service
from app.services.csv_service import build_events_csv, build_metrics_csv, build_motion_csv
from app.services.media_service import stream_file
from app.services.pdf_service import build_pdf
from app.services.pose_analysis_service import PoseAnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])

_pose_service = PoseAnalysisService()


@router.post("/upload", response_model=AnalysisResponse)
async def upload_and_analyze(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> AnalysisResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {file.content_type}")

    asset_id = uuid4().hex
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    source_path = UPLOAD_DIR / f"{asset_id}{suffix}"
    processed_path = PROCESSED_DIR / f"{asset_id}.mp4"
    thumbnail_path = PROCESSED_DIR / f"{asset_id}.jpg"
    tracking_path = PROCESSED_DIR / f"{asset_id}_tracking.mp4"
    sidebyside_path = PROCESSED_DIR / f"{asset_id}_sidebyside.mp4"
    slowmo_path = PROCESSED_DIR / f"{asset_id}_slowmo.mp4"

    with source_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    await file.close()

    try:
        metrics = await asyncio.to_thread(
            _pose_service.analyze_video,
            source_path,
            processed_path,
            thumbnail_path,
            tracking_path,
            sidebyside_path,
            slowmo_path,
        )
    except Exception as exc:
        for p in (source_path, processed_path, thumbnail_path, tracking_path, sidebyside_path, slowmo_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        raise HTTPException(status_code=422, detail=f"Analysis failed: {exc}") from exc

    metrics["assets"] = {
        "original_video_path": str(source_path),
        "processed_video_path": str(processed_path),
        "tracking_video_path": str(tracking_path) if tracking_path.exists() else None,
        "sidebyside_video_path": str(sidebyside_path) if sidebyside_path.exists() else None,
        "slowmo_video_path": str(slowmo_path) if slowmo_path.exists() else None,
        "thumbnail_path": str(thumbnail_path) if thumbnail_path.exists() else None,
    }

    title = f"Bowling Analysis {asset_id[:6]}"
    report = await report_service.insert_report(
        user_id=current_user["_id"],
        title=title,
        source_path=str(source_path),
        processed_path=str(processed_path) if processed_path.exists() else None,
        tracking_path=str(tracking_path) if tracking_path.exists() else None,
        sidebyside_path=str(sidebyside_path) if sidebyside_path.exists() else None,
        slowmo_path=str(slowmo_path) if slowmo_path.exists() else None,
        thumbnail_path=str(thumbnail_path) if thumbnail_path.exists() else None,
        summary=metrics.get("summary", {}),
        metrics=metrics,
    )

    pdf_path = REPORTS_DIR / f"report-{report['_id']}.pdf"
    try:
        await asyncio.to_thread(
            build_pdf, pdf_path, current_user.get("full_name", "Athlete"), report_service.to_response(report)
        )
        await report_service.set_pdf_path(report["_id"], str(pdf_path))
        report["pdf_report_path"] = str(pdf_path)
    except Exception:
        pass

    return AnalysisResponse(**report_service.to_response(report))


@router.get("/{report_id}/video")
async def processed_video(
    report_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    report = await report_service.get_report(report_id, current_user["_id"])
    path = report.get("processed_video_path")
    if not path:
        raise HTTPException(status_code=404, detail="Processed video not available")
    return stream_file(request, Path(path), "video/mp4")


@router.get("/{report_id}/tracking")
async def tracking_video(
    report_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    report = await report_service.get_report(report_id, current_user["_id"])
    path = report.get("tracking_video_path")
    if not path:
        raise HTTPException(status_code=404, detail="Joint-tracking video not available")
    return stream_file(request, Path(path), "video/mp4")


@router.get("/{report_id}/sidebyside")
async def sidebyside_video(
    report_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    report = await report_service.get_report(report_id, current_user["_id"])
    path = report.get("sidebyside_video_path")
    if not path:
        raise HTTPException(status_code=404, detail="Side-by-side video not available")
    return stream_file(request, Path(path), "video/mp4")


@router.get("/{report_id}/slowmo")
async def slowmo_video(
    report_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    report = await report_service.get_report(report_id, current_user["_id"])
    path = report.get("slowmo_video_path")
    if not path:
        raise HTTPException(status_code=404, detail="Slow-motion video not available")
    return stream_file(request, Path(path), "video/mp4")


@router.get("/{report_id}/source")
async def source_video(
    report_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    report = await report_service.get_report(report_id, current_user["_id"])
    path = report.get("source_video_path")
    if not path:
        raise HTTPException(status_code=404, detail="Original video not available")
    return stream_file(request, Path(path))


@router.get("/{report_id}/thumbnail")
async def thumbnail(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    report = await report_service.get_report(report_id, current_user["_id"])
    path = report.get("thumbnail_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    return FileResponse(Path(path), media_type="image/jpeg", filename=Path(path).name)


_CSV_BUILDERS = {
    "metrics": ("build_metrics_csv", build_metrics_csv),
    "motion": ("build_motion_csv", build_motion_csv),
    "events": ("build_events_csv", build_events_csv),
}


@router.get("/{report_id}/csv/{kind}")
async def export_csv(
    report_id: str,
    kind: str,
    current_user: dict = Depends(get_current_user),
):
    """Export a coach-friendly CSV for a report.

    `kind` is one of: metrics (flat summary), motion (frame-by-frame series),
    events (BFC/FFC/Release/Follow-through).
    """
    if kind not in _CSV_BUILDERS:
        raise HTTPException(status_code=400, detail=f"Unknown CSV kind: {kind}")
    report = await report_service.get_report(report_id, current_user["_id"])
    _, builder = _CSV_BUILDERS[kind]
    csv_text = builder(report)
    from fastapi.responses import Response

    filename = f"cricpose-{kind}-{report_id[:8]}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

