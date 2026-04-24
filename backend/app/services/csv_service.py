"""CSV builders for analysis reports.

Three coach-friendly CSV outputs:
- metrics.csv: one-row summary of all biomechanics signals + scores
- motion.csv: frame-by-frame joint angles / trajectory series
- events.csv: key delivery events (BFC, FFC, Release, Follow-through)
"""

from __future__ import annotations

import csv
import io
from typing import Iterable


def _dict_to_two_col(rows: Iterable[tuple[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    for key, value in rows:
        writer.writerow([key, "" if value is None else value])
    return buffer.getvalue()


def build_metrics_csv(report: dict) -> str:
    """Flat summary CSV: headline scores + joint metrics + classification + injury."""
    metrics = report.get("metrics", {}) or {}
    summary = metrics.get("summary", {}) or {}
    joint = metrics.get("joint_metrics", {}) or {}
    scores = metrics.get("scores", {}) or {}
    classification = metrics.get("classification", {}) or {}
    injury = metrics.get("injury_analysis", {}) or {}
    meta = metrics.get("video_meta", {}) or {}
    timing = metrics.get("timing_metrics", {}) or {}

    rows: list[tuple[str, object]] = [
        ("report_id", str(report.get("_id", ""))),
        ("title", report.get("title", "")),
        ("created_at", report.get("created_at").isoformat() if report.get("created_at") else ""),
        ("bowling_arm", meta.get("bowling_arm", "")),
        ("fps", meta.get("fps", "")),
        ("total_frames", meta.get("total_frames", "")),
        ("analyzed_frames", meta.get("analyzed_frames", "")),
    ]
    rows += [(f"summary.{k}", v) for k, v in summary.items()]
    rows += [(f"joint.{k}", v) for k, v in joint.items()]
    rows += [(f"score.{k}", v) for k, v in scores.items()]
    rows += [(f"timing.{k}", v) for k, v in timing.items()]
    rows += [
        ("classification.action_type", classification.get("action_type", "")),
        ("classification.action_label", classification.get("action_label", "")),
        ("classification.confidence", classification.get("confidence", "")),
        ("classification.shoulder_at_bfc_deg", classification.get("shoulder_at_bfc_deg", "")),
        ("classification.shoulder_at_ffc_deg", classification.get("shoulder_at_ffc_deg", "")),
        ("classification.shoulder_delta_deg", classification.get("shoulder_delta_deg", "")),
        ("injury.probability", injury.get("probability", "")),
        ("injury.band", injury.get("band", "")),
    ]
    contributors = injury.get("contributors") or []
    for idx, c in enumerate(contributors, start=1):
        rows.append((f"injury.contributor_{idx}", f"{c.get('label', '')} (+{c.get('weight', 0)})"))
    return _dict_to_two_col(rows)


def build_motion_csv(report: dict) -> str:
    """Wide-format frame-by-frame CSV joining every motion series by frame index."""
    metrics = report.get("metrics", {}) or {}
    motion = metrics.get("motion_series", {}) or {}

    # Collect series into a frame-indexed dict
    rows: dict[int, dict[str, object]] = {}

    def _merge(series: list[dict], column: str, value_key: str = "value") -> None:
        for point in series or []:
            frame = int(point.get("frame", 0))
            ts = point.get("timestamp")
            entry = rows.setdefault(frame, {"frame": frame, "timestamp": ts})
            entry[column] = point.get(value_key)
            if "timestamp" not in entry or entry["timestamp"] is None:
                entry["timestamp"] = ts

    _merge(motion.get("bowling_arm_angle", []), "bowling_arm_angle_deg")
    _merge(motion.get("shoulder_alignment", []), "shoulder_alignment_deg")
    _merge(motion.get("front_knee_bend", []), "front_knee_bend_deg")
    _merge(motion.get("back_knee_bend", []), "back_knee_bend_deg")
    _merge(motion.get("trunk_lateral_flexion", []), "trunk_lateral_flexion_deg")
    _merge(motion.get("pelvis_shoulder_separation", []), "pelvis_shoulder_separation_deg")

    for point in motion.get("wrist_trajectory", []) or []:
        frame = int(point.get("frame", 0))
        entry = rows.setdefault(frame, {"frame": frame, "timestamp": point.get("timestamp")})
        entry["wrist_x_norm"] = point.get("x")
        entry["wrist_y_norm"] = point.get("y")

    for point in motion.get("symmetry", []) or []:
        frame = int(point.get("frame", 0))
        entry = rows.setdefault(frame, {"frame": frame, "timestamp": point.get("timestamp")})
        entry["left_knee_deg"] = point.get("left")
        entry["right_knee_deg"] = point.get("right")

    for point in motion.get("risk_heatmap", []) or []:
        frame = int(point.get("frame", 0))
        entry = rows.setdefault(frame, {"frame": frame, "timestamp": point.get("timestamp")})
        entry["trunk_flex_deg"] = point.get("trunk_flex")
        entry["risk_band"] = point.get("band")

    columns = [
        "frame",
        "timestamp",
        "bowling_arm_angle_deg",
        "shoulder_alignment_deg",
        "front_knee_bend_deg",
        "back_knee_bend_deg",
        "trunk_lateral_flexion_deg",
        "pelvis_shoulder_separation_deg",
        "wrist_x_norm",
        "wrist_y_norm",
        "left_knee_deg",
        "right_knee_deg",
        "trunk_flex_deg",
        "risk_band",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for frame_idx in sorted(rows.keys()):
        writer.writerow(rows[frame_idx])
    return buffer.getvalue()


def build_events_csv(report: dict) -> str:
    """Events CSV with the 4 detected delivery events (BFC, FFC, Release, Follow-through)."""
    metrics = report.get("metrics", {}) or {}
    events = metrics.get("frame_events", []) or []

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["label", "frame", "timestamp_s", "confidence"])
    for event in events:
        writer.writerow(
            [
                event.get("label", ""),
                event.get("frame", ""),
                event.get("timestamp", ""),
                event.get("confidence", ""),
            ]
        )
    return buffer.getvalue()
