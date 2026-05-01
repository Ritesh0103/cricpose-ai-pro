import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile

from app.core.config import TEMP_DIR
from app.deps import get_current_user
from app.services.bowling_pipeline_service import BowlingPipelineService


router = APIRouter(prefix="/pipeline", tags=["data-driven-pipeline"])
_service = BowlingPipelineService()


@router.get("/data-layout")
async def data_layout(current_user: dict = Depends(get_current_user)) -> dict:
    return _service.data_layout()


@router.post("/process-all")
async def process_all(
    sample_fps: float = Query(8.0, ge=1.0, le=30.0),
    current_user: dict = Depends(get_current_user),
) -> dict:
    try:
        return _service.process_all(sample_fps=sample_fps)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/build-profiles")
async def build_profiles(current_user: dict = Depends(get_current_user)) -> dict:
    try:
        return _service.build_profiles()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/bootstrap-dataset")
async def bootstrap_dataset(current_user: dict = Depends(get_current_user)) -> dict:
    try:
        return _service.bootstrap_dataset()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/bowlers")
async def list_bowlers(current_user: dict = Depends(get_current_user)) -> dict:
    return {"bowlers": _service.list_bowlers()}


def _parse_selected_bowlers(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in value.split(",") if item.strip()]


@router.post("/analyze")
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    selected_bowlers: str | None = Form(None),
    sample_fps: float = Query(8.0, ge=1.0, le=30.0),
    current_user: dict = Depends(get_current_user),
) -> dict:
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    source_path = TEMP_DIR / f"pipeline-user-upload-{uuid4().hex}{suffix}"
    try:
        with source_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        base_url = str(request.base_url).rstrip("/")
        return _service.analyze_user_video(
            source_path,
            selected_bowlers=_parse_selected_bowlers(selected_bowlers),
            sample_fps=sample_fps,
            base_url=base_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
        source_path.unlink(missing_ok=True)
