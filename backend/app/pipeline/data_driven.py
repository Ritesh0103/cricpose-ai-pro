from __future__ import annotations

import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import (
    DATASETS_DIR,
    KEYPOINTS_DIR,
    PRO_BOWLERS_DIR,
    PROCESSED_FRAMES_DIR,
    PROFILES_DIR,
    STATIC_VIDEOS_DIR,
    USER_RAW_VIDEOS_DIR,
)
from app.pipeline.pose_detector import MediaPipePoseDetector, draw_pose_overlay
from app.pipeline.preprocessing import VIDEO_EXTENSIONS, extract_frames, iter_media_files


CORE_FEATURES = [
    "arm_angle",
    "release_angle",
    "shoulder_alignment",
    "pelvis_shoulder_separation",
    "spine_lateral_flexion",
    "knee_flexion",
    "knee_extension",
]

ADVANCED_FEATURES = [
    "arm_speed",
    "hip_rotation_speed",
    "runup_speed",
    "stride_length",
    "balance_score",
    "follow_through_balance",
    "head_stability",
    "elbow_extension",
    "wrist_velocity",
    "release_speed_estimate",
    "vGRF_estimate",
]

EVENT_COLUMNS = ["is_bfc", "is_ffc", "is_release", "is_follow_through"]
FEATURE_COLUMNS = CORE_FEATURES + ADVANCED_FEATURES
CSV_COLUMNS = ["frame_id", "timestamp", *FEATURE_COLUMNS, *EVENT_COLUMNS]

RADAR_MAP = {
    "Release Angle": "release_angle",
    "Front Knee Brace": "knee_extension",
    "Shoulder Alignment": "shoulder_alignment",
    "Hip Separation": "pelvis_shoulder_separation",
    "Arm Speed": "arm_speed",
    "Balance": "balance_score",
    "Run-up Consistency": "runup_speed",
    "Efficiency": "release_speed_estimate",
}


@dataclass(frozen=True)
class VideoRecord:
    video_id: str
    source_path: Path
    group: str
    bowler: str | None


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.strip().lower()).strip("_")


def _point(frame: dict, name: str) -> np.ndarray:
    point = frame["keypoints"][name]
    return np.array([float(point["x"]), float(point["y"])], dtype=float)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ab = a - b
    cb = c - b
    denom = float(np.linalg.norm(ab) * np.linalg.norm(cb))
    if denom == 0:
        return np.nan
    value = float(np.dot(ab, cb) / denom)
    return float(np.degrees(np.arccos(np.clip(value, -1.0, 1.0))))


def _line_angle(a: np.ndarray, b: np.ndarray) -> float:
    vec = b - a
    return float(np.degrees(np.arctan2(vec[1], vec[0] + np.finfo(float).eps)))


def _vertical_angle(upper: np.ndarray, lower: np.ndarray) -> float:
    vec = upper - lower
    return float(np.degrees(np.arctan2(abs(vec[0]), abs(vec[1]) + np.finfo(float).eps)))


def _mid(frame: dict, a: str, b: str) -> np.ndarray:
    return (_point(frame, a) + _point(frame, b)) / 2.0


def _infer_bowling_side(detections: list[dict]) -> str:
    left = min(_point(frame, "left_wrist")[1] for frame in detections)
    right = min(_point(frame, "right_wrist")[1] for frame in detections)
    return "right" if right < left else "left"


def _velocity(values: np.ndarray, fps: float) -> np.ndarray:
    if len(values) < 2:
        return np.zeros_like(values, dtype=float)
    return np.gradient(values.astype(float), 1.0 / fps)


def _detect_events(df: pd.DataFrame, profile_patterns: dict | None = None) -> dict[str, int]:
    n = len(df)
    if n == 0:
        return {"BFC": 0, "FFC": 0, "RELEASE": 0, "FOLLOW_THROUGH": 0}

    release = int(df["wrist_y"].idxmin()) if df["wrist_y"].notna().any() else None
    if release is None and profile_patterns:
        release = int(round(float(profile_patterns.get("RELEASE", 0.5)) * max(n - 1, 1)))
    if release is None:
        release = int(df["arm_speed"].idxmax()) if df["arm_speed"].notna().any() else int(n // 2)

    ankle_velocity = df["front_ankle_y_velocity"].to_numpy(dtype=float)
    search = df.iloc[: max(release + 1, 1)]
    if len(search):
        ffc = int(search["front_ankle_y"].idxmax())
        if np.isfinite(ankle_velocity[: release + 1]).any():
            local = int(np.nanargmin(np.abs(ankle_velocity[: max(release + 1, 1)])))
            ffc = min(local, release)
    elif profile_patterns:
        ffc = int(round(float(profile_patterns.get("FFC", 0.4)) * max(n - 1, 1)))
    else:
        ffc = max(0, release - 1)

    back_search = df.iloc[: max(ffc + 1, 1)]
    if len(back_search):
        bfc = int(back_search["back_ankle_y"].idxmax())
    elif profile_patterns:
        bfc = int(round(float(profile_patterns.get("BFC", 0.25)) * max(n - 1, 1)))
    else:
        bfc = 0

    follow = None
    if profile_patterns:
        follow = int(round(float(profile_patterns.get("FOLLOW_THROUGH", 0.8)) * max(n - 1, 1)))
    if follow is None:
        follow_candidates = df.index[df.index > release].tolist()
        follow = follow_candidates[-1] if follow_candidates else release

    return {
        "BFC": int(np.clip(bfc, 0, n - 1)),
        "FFC": int(np.clip(ffc, 0, n - 1)),
        "RELEASE": int(np.clip(release, 0, n - 1)),
        "FOLLOW_THROUGH": int(np.clip(follow, 0, n - 1)),
    }


def _interpolate_feature_frame(df: pd.DataFrame, profile: dict | None = None) -> pd.DataFrame:
    df = df.copy()
    for col in FEATURE_COLUMNS:
        if col not in df:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].interpolate(limit_direction="both")
        if df[col].isna().any() and profile:
            stat = profile.get("metrics", {}).get(col, {})
            if "mean" in stat:
                df[col] = df[col].fillna(float(stat["mean"]))
        df[col] = df[col].fillna(float(df[col].median()) if df[col].notna().any() else 0.0)
    for col in EVENT_COLUMNS:
        if col not in df:
            df[col] = 0
        df[col] = df[col].fillna(0).astype(int)
    return df[CSV_COLUMNS]


def _distribution(values: pd.Series) -> dict:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {key: 0.0 for key in ["mean", "std", "min", "max", "median", "p10", "p25", "p75", "p90"]}
    return {
        "mean": round(float(clean.mean()), 6),
        "std": round(float(clean.std(ddof=0)), 6),
        "min": round(float(clean.min()), 6),
        "max": round(float(clean.max()), 6),
        "median": round(float(clean.median()), 6),
        "p10": round(float(clean.quantile(0.10)), 6),
        "p25": round(float(clean.quantile(0.25)), 6),
        "p75": round(float(clean.quantile(0.75)), 6),
        "p90": round(float(clean.quantile(0.90)), 6),
    }


class DataDrivenBowlingPipeline:
    def data_layout(self) -> dict:
        return {
            "raw_videos": str(PRO_BOWLERS_DIR.parent),
            "pro_bowlers": str(PRO_BOWLERS_DIR),
            "users": str(USER_RAW_VIDEOS_DIR),
            "processed_frames": str(PROCESSED_FRAMES_DIR),
            "keypoints": str(KEYPOINTS_DIR),
            "datasets": str(DATASETS_DIR),
            "profiles": str(PROFILES_DIR),
            "static_videos": str(STATIC_VIDEOS_DIR),
        }

    def discover_videos(self) -> list[VideoRecord]:
        records: list[VideoRecord] = []
        for bowler_dir in sorted(p for p in PRO_BOWLERS_DIR.iterdir() if p.is_dir()):
            bowler = _safe_name(bowler_dir.name)
            for source in iter_media_files(bowler_dir):
                records.append(VideoRecord(f"{bowler}__{_safe_name(source.stem)}", source, "pro", bowler))
        for source in iter_media_files(USER_RAW_VIDEOS_DIR):
            records.append(VideoRecord(f"user__{_safe_name(source.stem)}", source, "user", None))
        return records

    def process_all(self, *, sample_fps: float) -> dict:
        records = self.discover_videos()
        if not records:
            raise ValueError(f"No videos found under {PRO_BOWLERS_DIR} or {USER_RAW_VIDEOS_DIR}")
        processed = []
        skipped = []
        for record in records:
            try:
                processed.append(self.process_video(record, sample_fps=sample_fps))
            except ValueError as exc:
                skipped.append({"video_id": record.video_id, "source_path": str(record.source_path), "reason": str(exc)})
                print(f"Skipping video after robust retries: {record.source_path} ({exc})")
        return {
            "data_layout": self.data_layout(),
            "processed_count": len(processed),
            "skipped_count": len(skipped),
            "videos": processed,
            "skipped": skipped,
        }

    def process_video(
        self,
        record: VideoRecord,
        *,
        sample_fps: float,
        closest_profile: dict | None = None,
    ) -> dict:
        frame_dir = PROCESSED_FRAMES_DIR / record.video_id
        keypoints_path = KEYPOINTS_DIR / f"{record.video_id}.json"
        dataset_path = DATASETS_DIR / f"{record.video_id}.csv"

        extraction = extract_frames(record.source_path, frame_dir, sample_fps=sample_fps)
        detector = MediaPipePoseDetector(static_image_mode=True, model_complexity=1)
        try:
            keypoints = detector.process_frame_dir(frame_dir, keypoints_path)
        finally:
            detector.close()

        if keypoints.get("detected_frames", 0) == 0 and extraction.sample_fps > 3.0:
            print(f"No pose keypoints detected for {record.video_id}; retrying frame extraction at sample_fps=3")
            extraction = extract_frames(record.source_path, frame_dir, sample_fps=3.0)
            detector = MediaPipePoseDetector(static_image_mode=True, model_complexity=1)
            try:
                keypoints = detector.process_frame_dir(frame_dir, keypoints_path)
            finally:
                detector.close()

        total_frames = int(keypoints.get("total_frames", 0) or 0)
        detected_frames = int(keypoints.get("detected_frames", 0) or 0)
        success_ratio = detected_frames / total_frames if total_frames else 0.0
        print(
            f"Keypoint validation for {record.video_id}: total frames={total_frames}, "
            f"detected frames={detected_frames}, success ratio={success_ratio:.4f}"
        )
        if detected_frames == 0:
            raise ValueError("No pose keypoints detected")
        if success_ratio < 0.05:
            print("Very low detection, but continuing pipeline")

        df, events = self.features_from_keypoints(keypoints, fps=extraction.sample_fps, closest_profile=closest_profile)
        df.to_csv(dataset_path, index=False)

        return {
            "video_id": record.video_id,
            "group": record.group,
            "bowler": record.bowler,
            "source_path": str(record.source_path),
            "keypoints_path": str(keypoints_path),
            "dataset_path": str(dataset_path),
            "events": events,
            "preprocessing": asdict(extraction),
        }

    def features_from_keypoints(
        self,
        keypoints: dict,
        *,
        fps: float,
        closest_profile: dict | None = None,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        detections = keypoints.get("detections", [])
        total_frames = int(keypoints.get("total_frames", len(detections)) or len(detections))
        detected_frames = len(detections)
        success_ratio = detected_frames / total_frames if total_frames else 0.0
        print(
            "Feature extraction keypoints: "
            f"total frames={total_frames}, detected frames={detected_frames}, "
            f"success ratio={success_ratio:.4f}"
        )
        if not detections:
            raise ValueError("No pose keypoints detected.")
        if success_ratio < 0.05:
            print("Very low detection, but continuing pipeline")

        side = _infer_bowling_side(detections)
        front = "left" if side == "right" else "right"
        back = "right" if side == "right" else "left"

        raw_rows = []
        for idx, frame in enumerate(detections):
            shoulder = _point(frame, f"{side}_shoulder")
            elbow = _point(frame, f"{side}_elbow")
            wrist = _point(frame, f"{side}_wrist")
            front_hip = _point(frame, f"{front}_hip")
            front_knee = _point(frame, f"{front}_knee")
            front_ankle = _point(frame, f"{front}_ankle")
            back_ankle = _point(frame, f"{back}_ankle")
            left_shoulder = _point(frame, "left_shoulder")
            right_shoulder = _point(frame, "right_shoulder")
            left_hip = _point(frame, "left_hip")
            right_hip = _point(frame, "right_hip")
            mid_shoulder = (left_shoulder + right_shoulder) / 2.0
            mid_hip = (left_hip + right_hip) / 2.0
            shoulder_angle = _line_angle(left_shoulder, right_shoulder)
            hip_angle = _line_angle(left_hip, right_hip)
            knee_angle = _angle(front_hip, front_knee, front_ankle)
            arm_line_angle = _vertical_angle(wrist, shoulder)
            raw_rows.append(
                {
                    "frame_id": idx,
                    "timestamp": idx / fps,
                    "arm_angle": _angle(shoulder, elbow, wrist),
                    "release_angle": arm_line_angle,
                    "shoulder_alignment": abs(shoulder_angle),
                    "pelvis_shoulder_separation": abs(shoulder_angle - hip_angle),
                    "spine_lateral_flexion": _vertical_angle(mid_shoulder, mid_hip),
                    "knee_flexion": knee_angle,
                    "knee_extension": 180.0 - knee_angle if np.isfinite(knee_angle) else np.nan,
                    "elbow_extension": _angle(shoulder, elbow, wrist),
                    "wrist_x": wrist[0],
                    "wrist_y": wrist[1],
                    "hip_x": mid_hip[0],
                    "hip_y": mid_hip[1],
                    "hip_angle": hip_angle,
                    "head_x": _mid(frame, "left_shoulder", "right_shoulder")[0],
                    "front_ankle_x": front_ankle[0],
                    "front_ankle_y": front_ankle[1],
                    "back_ankle_x": back_ankle[0],
                    "back_ankle_y": back_ankle[1],
                }
            )

        working = pd.DataFrame(raw_rows)
        working["arm_speed"] = np.abs(_velocity(working["arm_angle"].to_numpy(dtype=float), fps))
        working["hip_rotation_speed"] = np.abs(_velocity(working["hip_angle"].to_numpy(dtype=float), fps))
        working["runup_speed"] = np.abs(_velocity(working["hip_x"].to_numpy(dtype=float), fps))
        working["wrist_velocity"] = np.hypot(
            _velocity(working["wrist_x"].to_numpy(dtype=float), fps),
            _velocity(working["wrist_y"].to_numpy(dtype=float), fps),
        )
        working["release_speed_estimate"] = working["wrist_velocity"]
        working["stride_length"] = np.hypot(
            working["front_ankle_x"] - working["back_ankle_x"],
            working["front_ankle_y"] - working["back_ankle_y"],
        )
        working["front_ankle_y_velocity"] = _velocity(working["front_ankle_y"].to_numpy(dtype=float), fps)
        working["vGRF_estimate"] = np.abs(_velocity(_velocity(working["hip_y"].to_numpy(dtype=float), fps), fps))

        motion_spread = working[["hip_x", "hip_y"]].rolling(window=max(2, int(np.sqrt(len(working)))), min_periods=1).std()
        working["balance_score"] = 1.0 / (1.0 + motion_spread.mean(axis=1).fillna(0.0))
        working["follow_through_balance"] = working["balance_score"]
        working["head_stability"] = 1.0 / (
            1.0
            + working["head_x"]
            .rolling(window=max(2, int(np.sqrt(len(working)))), min_periods=1)
            .std()
            .fillna(0.0)
        )

        profile_patterns = (closest_profile or {}).get("event_frame_ratios")
        events = _detect_events(working, profile_patterns)
        for column in EVENT_COLUMNS:
            working[column] = 0
        working.loc[events["BFC"], "is_bfc"] = 1
        working.loc[events["FFC"], "is_ffc"] = 1
        working.loc[events["RELEASE"], "is_release"] = 1
        working.loc[events["FOLLOW_THROUGH"], "is_follow_through"] = 1

        return _interpolate_feature_frame(working, closest_profile), events

    def build_profiles(self) -> dict:
        profiles = {}
        for bowler_dir in sorted(p for p in PRO_BOWLERS_DIR.iterdir() if p.is_dir()):
            bowler = _safe_name(bowler_dir.name)
            csv_paths = sorted(DATASETS_DIR.glob(f"{bowler}__*.csv"))
            if not csv_paths:
                continue
            df = pd.concat([pd.read_csv(path) for path in csv_paths], ignore_index=True)
            profile = self._profile_from_dataframe(bowler, df, csv_paths)
            out_path = PROFILES_DIR / f"{bowler}.json"
            out_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
            profiles[bowler] = profile
        weights = self.learn_weights(profiles)
        (PROFILES_DIR / "metric_weights.json").write_text(json.dumps(weights, indent=2), encoding="utf-8")
        return {"profiles": list(profiles), "weights": weights, "profile_dir": str(PROFILES_DIR)}

    def _profile_from_dataframe(self, bowler: str, df: pd.DataFrame, csv_paths: list[Path]) -> dict:
        clean = df.copy()
        for col in FEATURE_COLUMNS:
            series = pd.to_numeric(clean[col], errors="coerce")
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if np.isfinite(iqr) and iqr > 0:
                clean = clean[(series >= q1 - 1.5 * iqr) & (series <= q3 + 1.5 * iqr)]
        if clean.empty:
            clean = df.copy()
        metrics = {col: _distribution(clean[col]) for col in FEATURE_COLUMNS}
        event_frame_ratios = {}
        for label, col in {
            "BFC": "is_bfc",
            "FFC": "is_ffc",
            "RELEASE": "is_release",
            "FOLLOW_THROUGH": "is_follow_through",
        }.items():
            frames = df.loc[df[col] == 1, "frame_id"]
            max_frame = max(float(df["frame_id"].max()), 1.0)
            event_frame_ratios[label] = round(float((frames / max_frame).median()), 6) if not frames.empty else 0.0
        return {
            "bowler": bowler,
            "source_csvs": [str(path) for path in csv_paths],
            "sample_count": int(len(clean)),
            "metrics": metrics,
            "event_frame_ratios": event_frame_ratios,
        }

    def learn_weights(self, profiles: dict[str, dict]) -> dict:
        if not profiles:
            return {}
        variances = {}
        for metric in FEATURE_COLUMNS:
            means = [profile["metrics"][metric]["mean"] for profile in profiles.values()]
            variances[metric] = float(np.var(means))
        total = sum(variances.values())
        if total == 0:
            count = len(variances) or 1
            return {metric: 1.0 / count for metric in variances}
        return {metric: round(value / total, 8) for metric, value in variances.items()}

    def list_bowlers(self) -> list[dict]:
        bowlers = []
        for path in sorted(PROFILES_DIR.glob("*.json")):
            if path.name == "metric_weights.json":
                continue
            profile = json.loads(path.read_text(encoding="utf-8"))
            bowlers.append({"id": profile["bowler"], "name": profile["bowler"].replace("_", " ").title()})
        return bowlers

    def analyze_upload(self, source_path: Path, selected_bowlers: list[str], *, sample_fps: float, base_url: str) -> dict:
        profiles = self._load_profiles(selected_bowlers)
        if not profiles:
            raise ValueError("No bowler profiles found. Run /api/pipeline/build-profiles first.")
        weights = self._load_weights()
        closest_profile = next(iter(profiles.values()))
        video_id = f"user__{_safe_name(source_path.stem)}"
        static_source = STATIC_VIDEOS_DIR / f"{video_id}{source_path.suffix.lower() or '.mp4'}"
        shutil.copyfile(source_path, static_source)
        record = VideoRecord(video_id, static_source, "user", None)
        processed = self.process_video(record, sample_fps=sample_fps, closest_profile=closest_profile)

        overlay_path = STATIC_VIDEOS_DIR / f"{video_id}_overlay.mp4"
        if static_source.suffix.lower() in VIDEO_EXTENSIONS:
            draw_pose_overlay(static_source, overlay_path)

        user_df = pd.read_csv(processed["dataset_path"])
        user_metrics = self._user_snapshot(user_df)
        pro_profile = self._merged_profile(profiles)
        return self._format_ui_output(
            user_metrics,
            user_df,
            pro_profile,
            profiles,
            weights,
            processed["events"],
            f"{base_url}/static/videos/{static_source.name}",
            f"{base_url}/static/videos/{overlay_path.name}" if overlay_path.exists() else None,
        )

    def _load_profiles(self, selected_bowlers: list[str]) -> dict[str, dict]:
        available = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in PROFILES_DIR.glob("*.json")
            if path.name != "metric_weights.json"
        }
        if selected_bowlers:
            selected = {_safe_name(name) for name in selected_bowlers}
            return {name: profile for name, profile in available.items() if name in selected}
        return available

    def _load_weights(self) -> dict:
        path = PROFILES_DIR / "metric_weights.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return self.learn_weights(self._load_profiles([]))

    def _merged_profile(self, profiles: dict[str, dict]) -> dict:
        merged = {"bowler": "Pro", "metrics": {}}
        for metric in FEATURE_COLUMNS:
            values = [profile["metrics"][metric]["mean"] for profile in profiles.values()]
            merged["metrics"][metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min([profile["metrics"][metric]["min"] for profile in profiles.values()])),
                "max": float(np.max([profile["metrics"][metric]["max"] for profile in profiles.values()])),
                "median": float(np.median(values)),
            }
        return merged

    def _user_snapshot(self, user_df: pd.DataFrame) -> dict:
        release_rows = user_df[user_df["is_release"] == 1]
        snapshot = release_rows.iloc[0] if not release_rows.empty else user_df.iloc[int(user_df["arm_speed"].idxmax())]
        values = {metric: float(snapshot[metric]) for metric in FEATURE_COLUMNS}
        values["runup_speed"] = float(user_df["runup_speed"].mean())
        values["follow_through_balance"] = float(user_df["follow_through_balance"].tail(max(1, int(np.sqrt(len(user_df))))).mean())
        return values

    def _similarity(self, value: float, stats: dict, weight: float) -> float:
        scale = float(stats.get("std") or np.std([stats.get("min", 0), stats.get("max", 0)]) or 1.0)
        return float(100.0 * math.exp(-(abs(value - float(stats["mean"])) / scale) * max(weight, np.finfo(float).eps)))

    def _format_ui_output(
        self,
        user_metrics: dict,
        user_df: pd.DataFrame,
        pro_profile: dict,
        selected_profiles: dict[str, dict],
        weights: dict,
        events: dict,
        video_url: str,
        overlay_video_url: str | None,
    ) -> dict:
        metric_rows = []
        similarities = []
        for metric in FEATURE_COLUMNS:
            stats = pro_profile["metrics"][metric]
            user_value = float(user_metrics[metric])
            delta = user_value - float(stats["mean"])
            similarity = self._similarity(user_value, stats, float(weights.get(metric, 0.0)))
            similarities.append(similarity)
            metric_rows.append(
                {
                    "name": metric.replace("_", " ").title(),
                    "user": round(user_value, 6),
                    "benchmark": round(float(stats["mean"]), 6),
                    "delta": round(delta, 6),
                    "similarity": round(similarity, 3),
                    "status": "within_profile_range"
                    if float(stats["min"]) <= user_value <= float(stats["max"])
                    else ("above_profile_range" if delta > 0 else "below_profile_range"),
                }
            )

        radar_labels = list(RADAR_MAP)
        user_radar = []
        pro_radar = []
        for label, metric in RADAR_MAP.items():
            stats = pro_profile["metrics"][metric]
            user_radar.append(round(self._similarity(float(user_metrics[metric]), stats, float(weights.get(metric, 0.0))), 3))
            pro_radar.append(100.0)

        weighted = [
            row["similarity"] * float(weights.get(row["name"].lower().replace(" ", "_"), 0.0))
            for row in metric_rows
        ]
        total_weight = sum(weights.get(metric, 0.0) for metric in FEATURE_COLUMNS) or 1.0
        overall = sum(weighted) / total_weight
        efficiency_metrics = ["release_angle", "arm_speed", "release_speed_estimate", "elbow_extension"]
        balance_metrics = ["balance_score", "follow_through_balance", "head_stability"]
        consistency_metrics = ["runup_speed", "stride_length", "pelvis_shoulder_separation"]

        def group_score(metrics: list[str]) -> float:
            scores = [
                self._similarity(float(user_metrics[m]), pro_profile["metrics"][m], float(weights.get(m, 0.0)))
                for m in metrics
            ]
            return float(np.mean(scores)) if scores else 0.0

        deviations = sorted(
            metric_rows,
            key=lambda item: (100.0 - item["similarity"]) * float(weights.get(item["name"].lower().replace(" ", "_"), 0.0)),
            reverse=True,
        )
        insights = [
            f"{item['name']} is {abs(item['delta']):.3g} away from the selected profile mean."
            for item in deviations
            if item["status"] != "within_profile_range"
        ]
        if not insights:
            insights = ["The delivery sits inside the selected bowler profile ranges across the learned metrics."]

        injury_factors = [
            {"metric": item["name"], "delta": item["delta"], "similarity": item["similarity"]}
            for item in deviations[: max(1, int(np.sqrt(len(deviations))))]
            if item["status"] != "within_profile_range"
        ]
        injury_score = float(np.mean([100.0 - factor["similarity"] for factor in injury_factors])) if injury_factors else 0.0

        return {
            "summary": {
                "overall_score": round(float(overall), 3),
                "efficiency": round(group_score(efficiency_metrics), 3),
                "balance": round(group_score(balance_metrics), 3),
                "consistency": round(group_score(consistency_metrics), 3),
            },
            "radar": {
                "labels": radar_labels,
                "datasets": [
                    {"name": "You", "values": user_radar},
                    {"name": "Pro", "values": pro_radar},
                    *[
                        {
                            "name": name.replace("_", " ").title(),
                            "values": [
                                round(
                                    self._similarity(
                                        profile["metrics"][metric]["mean"],
                                        pro_profile["metrics"][metric],
                                        float(weights.get(metric, 0.0)),
                                    ),
                                    3,
                                )
                                for metric in RADAR_MAP.values()
                            ],
                        }
                        for name, profile in selected_profiles.items()
                    ],
                ],
            },
            "metrics": metric_rows,
            "time_series": {
                "arm_angle": user_df["arm_angle"].round(6).tolist(),
                "knee_flexion": user_df["knee_flexion"].round(6).tolist(),
                "pelvis_separation": user_df["pelvis_shoulder_separation"].round(6).tolist(),
            },
            "distribution": _distribution(pd.Series(similarities)),
            "insights": insights,
            "injury_risk": {"score": round(injury_score, 3), "factors": injury_factors},
            "events": {key: int(value) for key, value in events.items() if key != "FOLLOW_THROUGH"},
            "video": {"url": video_url, "overlay_url": overlay_video_url},
        }
