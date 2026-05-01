from __future__ import annotations

from pathlib import Path

from app.core.config import PRO_BOWLERS_DIR
from app.pipeline.data_driven import DataDrivenBowlingPipeline
from app.pipeline.preprocessing import download_and_prepare_datasets


class BowlingPipelineService:
    """Service wrapper for the CSV/profile driven bowling pipeline."""

    def __init__(self) -> None:
        self._pipeline = DataDrivenBowlingPipeline()

    def data_layout(self) -> dict:
        return self._pipeline.data_layout()

    def process_all(self, *, sample_fps: float) -> dict:
        return self._pipeline.process_all(sample_fps=sample_fps)

    def build_profiles(self) -> dict:
        return self._pipeline.build_profiles()

    def bootstrap_dataset(self) -> dict:
        preparation = download_and_prepare_datasets(PRO_BOWLERS_DIR)
        processed = self.process_all(sample_fps=6.0)
        profiles = self.build_profiles()
        videos_processed = int(processed.get("processed_count", 0))
        profiles_created = len(profiles.get("profiles", []))
        print(
            "Kaggle bootstrap complete: "
            f"processed videos={videos_processed}, profiles created={profiles_created}"
        )
        return {
            "videos_processed": videos_processed,
            "profiles_created": profiles_created,
            "status": "ready",
            "logs": {
                "total_videos_found": preparation.get("total_videos_found", 0),
                "valid_videos": preparation.get("valid_videos", 0),
                "skipped_videos": preparation.get("skipped_videos", 0),
                "processed_videos": videos_processed,
            },
            "preparation": preparation,
        }

    def list_bowlers(self) -> list[dict]:
        return self._pipeline.list_bowlers()

    def analyze_user_video(
        self,
        source_path: Path,
        *,
        selected_bowlers: list[str],
        sample_fps: float,
        base_url: str,
    ) -> dict:
        return self._pipeline.analyze_upload(
            source_path,
            selected_bowlers,
            sample_fps=sample_fps,
            base_url=base_url,
        )
