from __future__ import annotations

import importlib
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
KAGGLE_DATASETS = (
    "sureshmaheshwari021/cricket-dataset",
    "bigyansubedi/cricket-bowling-action-recognition",
)

logger = logging.getLogger("cricpose.pipeline.preprocessing")


@dataclass(frozen=True)
class FrameExtractionResult:
    source_path: str
    output_dir: str
    fps: float
    sample_fps: float
    original_frames: int
    extracted_frames: int
    width: int
    height: int


def iter_media_files(root: Path) -> list[Path]:
    """Return all supported videos/images under the Kaggle raw data folder."""
    if not root.exists():
        return []
    supported = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in supported)


def iter_video_files(root: Path) -> list[Path]:
    """Return supported video files under a folder."""
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)


def _ensure_kagglehub():
    try:
        return importlib.import_module("kagglehub")
    except ImportError:
        logger.info("kagglehub not found; installing into current Python environment")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "kagglehub"],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("kagglehub is not installed and automatic installation failed.") from exc
        return importlib.import_module("kagglehub")


def _arm_group_from_path(path: Path) -> str:
    haystack = " ".join(part.lower().replace("-", "_") for part in path.parts)
    left_tokens = ("left_arm", "leftarm", "left hand", "left_hand", "lhb", "left")
    right_tokens = ("right_arm", "rightarm", "right hand", "right_hand", "rhb", "right")
    if any(token in haystack for token in left_tokens):
        return "generic_left"
    if any(token in haystack for token in right_tokens):
        return "generic_right"
    return "generic_unknown"


def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")
    return cleaned or "video"


def _video_duration_seconds(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return 0.0
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps <= 0 or frames <= 0:
            ok, frame = cap.read()
            return 0.0 if not ok or frame is None else 2.0
        return frames / fps
    finally:
        cap.release()


def _is_valid_video(path: Path, *, min_duration_s: float = 2.0) -> tuple[bool, str | None]:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return False, "corrupted_or_unreadable"
        ok, frame = cap.read()
        if not ok or frame is None:
            return False, "no_decodable_frames"
    finally:
        cap.release()

    duration = _video_duration_seconds(path)
    if duration < min_duration_s:
        return False, "too_short"
    return True, None


def _convert_to_mp4(source: Path, target: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg missing; cannot convert %s", source)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(target),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.warning("ffmpeg conversion failed for %s: %s", source, result.stderr[-500:])
        target.unlink(missing_ok=True)
        return False
    return True


def download_and_prepare_datasets(raw_pro_bowlers_dir: Path) -> dict:
    """Download public Kaggle cricket datasets and normalize videos for the pipeline.

    Videos are grouped into generic left/right/unknown bowler folders because these
    datasets usually encode bowling-arm labels more reliably than real bowler names.
    """
    kagglehub = _ensure_kagglehub()
    downloaded_roots: list[Path] = []
    for dataset in KAGGLE_DATASETS:
        path = Path(kagglehub.dataset_download(dataset))
        downloaded_roots.append(path)
        logger.info("Downloaded Kaggle dataset %s to %s", dataset, path)

    raw_pro_bowlers_dir.mkdir(parents=True, exist_ok=True)
    for group in ("generic_left", "generic_right", "generic_unknown"):
        (raw_pro_bowlers_dir / group).mkdir(parents=True, exist_ok=True)

    source_videos: list[Path] = []
    for root in downloaded_roots:
        source_videos.extend(iter_video_files(root))

    total_found = len(source_videos)
    valid_videos = 0
    skipped: list[dict] = []
    prepared: list[dict] = []

    for index, source in enumerate(source_videos, start=1):
        group = _arm_group_from_path(source)
        target_dir = raw_pro_bowlers_dir / group
        dataset_prefix = _safe_stem(source.parents[0].name)
        target = target_dir / f"{dataset_prefix}_{_safe_stem(source.stem)}_{index}.mp4"
        target.unlink(missing_ok=True)

        if source.suffix.lower() == ".mp4":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            converted = _convert_to_mp4(source, target)
            if not converted:
                skipped.append({"source": str(source), "reason": "ffmpeg_conversion_failed"})
                continue

        ok, reason = _is_valid_video(target)
        if not ok:
            target.unlink(missing_ok=True)
            skipped.append({"source": str(source), "target": str(target), "reason": reason})
            continue

        valid_videos += 1
        prepared.append({"source": str(source), "target": str(target), "group": group})

    summary = {
        "datasets": list(KAGGLE_DATASETS),
        "downloaded_paths": [str(path) for path in downloaded_roots],
        "total_videos_found": total_found,
        "valid_videos": valid_videos,
        "skipped_videos": len(skipped),
        "prepared_videos": prepared,
        "skipped": skipped,
    }
    message = (
        f"Kaggle bootstrap: total videos found={total_found}, valid videos={valid_videos}, "
        f"skipped videos={len(skipped)}"
    )
    print(message)
    logger.info(message)
    return summary


def extract_frames(
    source_path: Path,
    output_dir: Path,
    *,
    sample_fps: float = 8.0,
    resize: tuple[int, int] = (640, 640),
) -> FrameExtractionResult:
    """Extract normalized JPG frames from a video or copy a single image frame.

    Images and videos both end up as resized RGB-compatible JPG files, which keeps
    the downstream pose step independent from the original Kaggle file format.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_frame in output_dir.glob("*.jpg"):
        old_frame.unlink(missing_ok=True)
    suffix = source_path.suffix.lower()
    width, height = resize

    if suffix in IMAGE_EXTENSIONS:
        frame = cv2.imread(str(source_path))
        if frame is None:
            raise ValueError(f"Could not open image: {source_path}")
        resized = cv2.resize(frame, resize, interpolation=cv2.INTER_AREA)
        out_path = output_dir / "frame_000001.jpg"
        cv2.imwrite(str(out_path), resized)
        return FrameExtractionResult(str(source_path), str(output_dir), 1.0, 1.0, 1, 1, width, height)

    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {source_path}")

    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total / source_fps if source_fps > 0 else 0.0
    effective_sample_fps = 3.0 if duration >= 60.0 or total >= 1800 else sample_fps
    if effective_sample_fps != sample_fps:
        print(
            "Large video detected; using adaptive sample_fps=3 "
            f"(duration={duration:.2f}s, frames={total})"
        )
    step = max(1, int(round(source_fps / max(effective_sample_fps, 0.1))))
    extracted = 0
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % step == 0:
                resized = cv2.resize(frame, resize, interpolation=cv2.INTER_AREA)
                out_path = output_dir / f"frame_{extracted + 1:06d}.jpg"
                cv2.imwrite(str(out_path), resized)
                extracted += 1
            frame_index += 1
    finally:
        cap.release()

    if extracted == 0:
        raise ValueError(f"No frames extracted from: {source_path}")

    return FrameExtractionResult(
        str(source_path),
        str(output_dir),
        source_fps,
        effective_sample_fps,
        total,
        extracted,
        width,
        height,
    )
