from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean

import numpy as np


def _pt(frame: dict, name: str) -> tuple[float, float]:
    kp = frame["keypoints"][name]
    return float(kp["x"]), float(kp["y"])


def _angle(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    ab = (a[0] - b[0], a[1] - b[1])
    cb = (c[0] - b[0], c[1] - b[1])
    denom = math.hypot(*ab) * math.hypot(*cb)
    if denom == 0:
        return 0.0
    cos_value = max(-1.0, min(1.0, (ab[0] * cb[0] + ab[1] * cb[1]) / denom))
    return math.degrees(math.acos(cos_value))


def _line_vs_vertical(upper: tuple[float, float], lower: tuple[float, float]) -> float:
    dx = upper[0] - lower[0]
    dy = upper[1] - lower[1]
    return math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))


def _release_frame(detections: list[dict], side: str) -> int:
    wrist = f"{side}_wrist"
    return int(np.argmin([_pt(frame, wrist)[1] for frame in detections]))


def infer_bowling_side(detections: list[dict]) -> str:
    left_peak = min(_pt(frame, "left_wrist")[1] for frame in detections)
    right_peak = min(_pt(frame, "right_wrist")[1] for frame in detections)
    return "right" if right_peak < left_peak else "left"


def extract_bowling_features(keypoint_payload: dict, *, assumed_fps: float = 8.0) -> dict:
    detections = keypoint_payload.get("detections", [])
    if len(detections) < 3:
        raise ValueError("Too few detected pose frames to extract bowling features.")

    side = infer_bowling_side(detections)
    opposite = "left" if side == "right" else "right"
    release_idx = _release_frame(detections, side)
    release = detections[release_idx]

    arm_angles = []
    knee_angles = []
    spine_angles = []
    hip_x = []
    for frame in detections:
        shoulder = _pt(frame, f"{side}_shoulder")
        elbow = _pt(frame, f"{side}_elbow")
        wrist = _pt(frame, f"{side}_wrist")
        hip = _pt(frame, f"{opposite}_hip")
        knee = _pt(frame, f"{opposite}_knee")
        ankle = _pt(frame, f"{opposite}_ankle")
        mid_shoulder = (
            (_pt(frame, "left_shoulder")[0] + _pt(frame, "right_shoulder")[0]) / 2.0,
            (_pt(frame, "left_shoulder")[1] + _pt(frame, "right_shoulder")[1]) / 2.0,
        )
        mid_hip = (
            (_pt(frame, "left_hip")[0] + _pt(frame, "right_hip")[0]) / 2.0,
            (_pt(frame, "left_hip")[1] + _pt(frame, "right_hip")[1]) / 2.0,
        )
        arm_angles.append(_angle(shoulder, elbow, wrist))
        knee_angles.append(_angle(hip, knee, ankle))
        spine_angles.append(_line_vs_vertical(mid_shoulder, mid_hip))
        hip_x.append(mid_hip[0])

    shoulder = _pt(release, f"{side}_shoulder")
    wrist = _pt(release, f"{side}_wrist")
    release_angle = math.degrees(math.atan2(abs(wrist[0] - shoulder[0]), -(wrist[1] - shoulder[1]) + 1e-6))

    window = min(len(hip_x) - 1, max(2, int(assumed_fps * 0.75)))
    runup_speed_norm_per_s = abs(hip_x[min(window, len(hip_x) - 1)] - hip_x[0]) / max(window / assumed_fps, 1e-6)

    return {
        "bowling_side": side,
        "detected_frames": len(detections),
        "release_frame_index": release_idx,
        "arm_angle_deg": round(float(max(arm_angles)), 2),
        "release_angle_deg": round(float(release_angle), 2),
        "runup_speed_normalized_per_s": round(float(runup_speed_norm_per_s), 4),
        "knee_bend_deg": round(float(180.0 - knee_angles[release_idx]), 2),
        "spine_alignment_deg": round(float(spine_angles[release_idx]), 2),
        "series": {
            "arm_angle_deg": [round(float(v), 2) for v in arm_angles],
            "knee_angle_deg": [round(float(v), 2) for v in knee_angles],
            "spine_alignment_deg": [round(float(v), 2) for v in spine_angles],
        },
    }


REFERENCE_METRICS = [
    "arm_angle_deg",
    "release_angle_deg",
    "runup_speed_normalized_per_s",
    "knee_bend_deg",
    "spine_alignment_deg",
]


def build_reference_model(feature_payloads: list[dict], output_path: Path) -> dict:
    if not feature_payloads:
        raise ValueError("No feature payloads supplied for pro reference model.")
    model = {
        "sample_count": len(feature_payloads),
        "metrics": {},
        "notes": [
            "Use only good-quality professional bowling clips/images in data/raw_videos before building this model.",
            "Single-camera speed is normalized image-space speed; calibrate with pitch markers for real m/s.",
        ],
    }
    for metric in REFERENCE_METRICS:
        values = [float(payload[metric]) for payload in feature_payloads if metric in payload]
        model["metrics"][metric] = {
            "mean": round(mean(values), 3),
            "std": round(float(np.std(values)), 3),
            "ideal_min": round(float(np.percentile(values, 20)), 3),
            "ideal_max": round(float(np.percentile(values, 80)), 3),
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return model


def compare_to_reference(user_features: dict, reference_model: dict) -> dict:
    deviations = {}
    mistakes = []
    feedback = []

    for metric, stats in reference_model.get("metrics", {}).items():
        athlete = float(user_features.get(metric, 0.0))
        ideal = float(stats["mean"])
        delta = round(athlete - ideal, 2)
        deviations[metric] = {
            "athlete": athlete,
            "reference": ideal,
            "delta": delta,
            "status": "good" if stats["ideal_min"] <= athlete <= stats["ideal_max"] else "needs_work",
        }

    arm = deviations.get("arm_angle_deg")
    if arm and arm["delta"] < -7:
        mistakes.append("Bowling arm is not reaching the professional extension range.")
        feedback.append(f"Increase arm angle by about {abs(arm['delta']):.0f} degrees.")

    release = deviations.get("release_angle_deg")
    if release and abs(release["delta"]) > 8:
        direction = "more upright" if release["delta"] > 0 else "slightly wider"
        mistakes.append("Release angle differs from the professional reference.")
        feedback.append(f"Make the release {direction} by roughly {abs(release['delta']):.0f} degrees.")

    knee = deviations.get("knee_bend_deg")
    if knee and knee["delta"] > 8:
        mistakes.append("Front leg is bending too much at release.")
        feedback.append("Improve front leg stability and brace earlier through front-foot contact.")

    spine = deviations.get("spine_alignment_deg")
    if spine and spine["delta"] > 7:
        mistakes.append("Spine alignment shows excessive lateral lean.")
        feedback.append(f"Reduce sideways spine lean by about {abs(spine['delta']):.0f} degrees.")

    speed = deviations.get("runup_speed_normalized_per_s")
    if speed and speed["delta"] < -0.04:
        mistakes.append("Run-up momentum is below the professional reference.")
        feedback.append("Build a smoother, faster approach while keeping head and trunk stable.")

    if not feedback:
        feedback.append("Bowling mechanics are close to the professional reference. Keep reinforcing consistency.")

    score = 100.0
    for item in deviations.values():
        ref = max(abs(float(item["reference"])), 1.0)
        score -= min(18.0, abs(float(item["delta"])) / ref * 35.0)

    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "deviations": deviations,
        "mistakes": mistakes,
        "feedback": feedback,
    }
