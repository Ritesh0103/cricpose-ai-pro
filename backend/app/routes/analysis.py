import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.core.config import ALLOWED_CONTENT_TYPES, PROCESSED_DIR, REPORTS_DIR, UPLOAD_DIR
from app.deps import get_current_user
from app.models import AnalysisResponse
from app.services import report_service
from app.services.csv_service import build_events_csv, build_metrics_csv, build_motion_csv
from app.services.demo_service import build_demo_metrics
from app.services.media_service import stream_file
from app.services.pdf_service import build_pdf
from app.services.pose_analysis_service import PoseAnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = logging.getLogger("cricpose.analysis")

_pose_service = PoseAnalysisService()

# Hard upload cap (bytes). Raises 413 before we spend MediaPipe cycles on huge clips.
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


def _classify_analysis_error(exc: Exception) -> tuple[int, str]:
    """Map raw analyzer exceptions to (status_code, user_facing_message)."""
    msg = str(exc)
    lower = msg.lower()
    if "no bowler detected" in lower or "no human detected" in lower:
        return (
            422,
            "No bowler was detected in the uploaded clip. Please upload a clearer delivery shot "
            "with the full body visible.",
        )
    if "could not open" in lower or "corrupt" in lower or "unable to open" in lower:
        return 422, "The video file appears corrupted or uses an unsupported codec (try mp4 H.264)."
    if "video too short" in lower or "too few frames" in lower:
        return 422, "Clip is too short — please upload at least 1 second of footage."
    return 500, f"Analysis engine error: {msg[:200]}"


async def _process_analysis(
    *,
    report_id,
    user_full_name: str,
    source_path: Path,
    processed_path: Path,
    thumbnail_path: Path,
    tracking_path: Path,
    sidebyside_path: Path,
    slowmo_path: Path,
) -> None:
    """Background task: run pose analysis + PDF, update the report with final metrics."""
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
        logger.exception("Pose analysis failed for report=%s: %s", report_id, exc)
        _code, friendly = _classify_analysis_error(exc)
        for p in (processed_path, thumbnail_path, tracking_path, sidebyside_path, slowmo_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        await report_service.update_processing_result(
            report_id, status="failed", error=friendly
        )
        return

    metrics["assets"] = {
        "original_video_path": str(source_path),
        "processed_video_path": str(processed_path) if processed_path.exists() else None,
        "tracking_video_path": str(tracking_path) if tracking_path.exists() else None,
        "sidebyside_video_path": str(sidebyside_path) if sidebyside_path.exists() else None,
        "slowmo_video_path": str(slowmo_path) if slowmo_path.exists() else None,
        "thumbnail_path": str(thumbnail_path) if thumbnail_path.exists() else None,
    }

    await report_service.update_processing_result(
        report_id,
        status="done",
        processed_path=str(processed_path) if processed_path.exists() else None,
        tracking_path=str(tracking_path) if tracking_path.exists() else None,
        sidebyside_path=str(sidebyside_path) if sidebyside_path.exists() else None,
        slowmo_path=str(slowmo_path) if slowmo_path.exists() else None,
        thumbnail_path=str(thumbnail_path) if thumbnail_path.exists() else None,
        summary=metrics.get("summary", {}),
        metrics=metrics,
    )

    # PDF is a nice-to-have; never block the status transition on PDF failure.
    pdf_path = REPORTS_DIR / f"report-{report_id}.pdf"
    try:
        # We have to re-fetch the report to get the _url fields populated for the PDF.
        db = report_service.get_db()
        report_doc = await db.reports.find_one({"_id": report_id})
        if report_doc:
            await asyncio.to_thread(
                build_pdf,
                pdf_path,
                user_full_name or "Athlete",
                report_service.to_response(report_doc),
            )
            await report_service.set_pdf_path(report_id, str(pdf_path))
    except Exception as exc:  # pragma: no cover
        logger.warning("PDF build skipped for report=%s: %s", report_id, exc)


@router.post("/upload", response_model=AnalysisResponse)
async def upload_and_analyze(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> AnalysisResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported video format: {file.content_type}. "
                "Please upload mp4, mov, webm, or m4v."
            ),
        )

    asset_id = uuid4().hex
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    source_path = UPLOAD_DIR / f"{asset_id}{suffix}"
    processed_path = PROCESSED_DIR / f"{asset_id}.mp4"
    thumbnail_path = PROCESSED_DIR / f"{asset_id}.jpg"
    tracking_path = PROCESSED_DIR / f"{asset_id}_tracking.mp4"
    sidebyside_path = PROCESSED_DIR / f"{asset_id}_sidebyside.mp4"
    slowmo_path = PROCESSED_DIR / f"{asset_id}_slowmo.mp4"

    total_bytes = 0
    try:
        with source_path.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"Video exceeds the 200 MB per-upload cap "
                            f"(you sent {total_bytes // (1024*1024)} MB). "
                            "Please trim to a 5-20 second delivery clip."
                        ),
                    )
                buffer.write(chunk)
    except HTTPException:
        source_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        logger.exception("Upload stream failed for %s: %s", file.filename, exc)
        source_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
    finally:
        await file.close()

    if total_bytes == 0:
        source_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    logger.info(
        "Upload accepted: user=%s file=%s size=%.2f MB — spawning background analysis",
        current_user.get("email", "?"),
        file.filename,
        total_bytes / (1024 * 1024),
    )

    # Create the report shell with status=processing so the frontend can start polling
    # immediately. The heavy MediaPipe + PDF work runs in a detached asyncio task so the
    # HTTP request returns in ~milliseconds and the Kubernetes ingress can't time it out.
    title = f"Bowling Analysis {asset_id[:6]}"
    report = await report_service.insert_report(
        user_id=current_user["_id"],
        title=title,
        source_path=str(source_path),
        processed_path=None,
        tracking_path=None,
        sidebyside_path=None,
        slowmo_path=None,
        thumbnail_path=None,
        summary={},
        metrics={"video_meta": {"pending": True}},
        status="processing",
    )

    asyncio.create_task(
        _process_analysis(
            report_id=report["_id"],
            user_full_name=current_user.get("full_name", "Athlete"),
            source_path=source_path,
            processed_path=processed_path,
            thumbnail_path=thumbnail_path,
            tracking_path=tracking_path,
            sidebyside_path=sidebyside_path,
            slowmo_path=slowmo_path,
        )
    )

    return AnalysisResponse(**report_service.to_response(report))


@router.get("/{report_id}/status", response_model=AnalysisResponse)
async def analysis_status(
    report_id: str,
    current_user: dict = Depends(get_current_user),
) -> AnalysisResponse:
    """Poll endpoint: returns the current state of a background analysis job.

    Frontend polls this every ~2s while status == "processing". When status flips to
    "done" the full metrics payload is available; if "failed" the `error` field carries
    the user-friendly reason.
    """
    report = await report_service.get_report(report_id, current_user["_id"])
    return AnalysisResponse(**report_service.to_response(report))


@router.post("/demo", response_model=AnalysisResponse)
async def run_demo_analysis(current_user: dict = Depends(get_current_user)) -> AnalysisResponse:
    """Create a demo report using hand-tuned synthetic metrics.

    Lets users explore the full dashboard, compare page, PDF + CSV exports without uploading a
    real bowling clip. The report is flagged with ``is_demo: True`` in its metrics dict.
    """
    metrics = build_demo_metrics()
    summary = metrics.get("summary", {})
    title = f"Demo Analysis {datetime.now(timezone.utc).strftime('%H%M%S')}"
    report = await report_service.insert_report(
        user_id=current_user["_id"],
        title=title,
        source_path="",
        processed_path=None,
        tracking_path=None,
        sidebyside_path=None,
        slowmo_path=None,
        thumbnail_path=None,
        summary=summary,
        metrics=metrics,
    )
    pdf_path = REPORTS_DIR / f"report-{report['_id']}.pdf"
    try:
        await asyncio.to_thread(
            build_pdf,
            pdf_path,
            current_user.get("full_name", "Athlete"),
            report_service.to_response(report),
        )
        await report_service.set_pdf_path(report["_id"], str(pdf_path))
        report["pdf_report_path"] = str(pdf_path)
    except Exception as exc:  # pragma: no cover
        logger.warning("Demo PDF build skipped: %s", exc)
    logger.info("Demo analysis created: id=%s user=%s", report["_id"], current_user.get("email"))
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

    filename = f"cricpose-{kind}-{report_id[:8]}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

