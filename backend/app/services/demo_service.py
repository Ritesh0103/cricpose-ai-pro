"""Demo analysis factory.

When a user has no real bowling video but wants to explore the platform end-to-end,
the demo endpoint materialises a realistic analysis payload using hand-tuned metrics
that match what a quality single-camera clip would produce. The payload is stored as
a normal report so every downstream feature (PDF, CSVs, compare, dashboard trends)
works exactly like a real analysis. Demo reports are tagged with ``is_demo: True``.
"""

from __future__ import annotations

import math
import random
from typing import Any

# Literature-backed "quality amateur bowler" metric targets. Slight per-invocation
# jitter so repeated demo clicks produce varying but plausible data.
_BASE = {
    "shoulder_alignment_deg": 10.4,
    "pelvis_shoulder_separation_deg": 41.6,
    "trunk_lateral_flexion_deg": 24.2,
    "front_knee_flexion_ffc_deg": 158.0,
    "front_knee_flexion_br_deg": 170.4,
    "knee_flexion_change_deg": -12.4,
    "stride_length_m": 1.88,
    "runup_speed_kph": 22.3,
    "release_speed_kph": 134.8,
    "release_angle_deg": 13.6,
    "release_height_m": 2.22,
    "wrist_velocity_mps": 17.1,
    "hip_rotation_speed_dps": 820.0,
    "landing_balance_score": 74.0,
    "symmetry_score": 81.0,
    "vGRF_body_weights": 5.1,
}


def _jitter(value: float, pct: float = 0.04) -> float:
    """Return a small +/- pct fluctuation around value."""
    return round(value * (1 + random.uniform(-pct, pct)), 2)


def build_demo_metrics() -> dict[str, Any]:
    """Return a complete demo metrics dict matching pose_analysis_service schema."""
    random.seed()

    # Core joint metrics (jittered)
    joint = {k: _jitter(v) for k, v in _BASE.items()}
    joint["vGRF_newtons"] = round(75.0 * (9.81 + joint["vGRF_body_weights"] * 9.81), 1)

    # Frame timing proxy — pretend 120 frames @ 30 fps
    fps = 30.0
    total_frames = 120
    ffc_idx = 72
    release_idx = 84
    follow_idx = 99
    bfc_idx = 52

    def _series(base: float, amp: float, phase: float = 0.0, noise: float = 2.0) -> list[dict]:
        out = []
        for i in range(total_frames):
            t = i / fps
            val = base + amp * math.sin(2 * math.pi * (t / 2.0) + phase) + random.uniform(-noise, noise)
            out.append({"frame": i, "timestamp": round(t, 3), "value": round(val, 2)})
        return out

    motion_series = {
        "bowling_arm_angle": [
            {"frame": i, "timestamp": round(i / fps, 3),
             "value": round(20 + 150 * math.sin(math.pi * min(i / 90.0, 1.0)) + random.uniform(-3, 3), 2)}
            for i in range(total_frames)
        ],
        "shoulder_alignment": _series(joint["shoulder_alignment_deg"], 4.0, 0.4),
        "front_knee_bend": _series(155, 10.0, 0.2, 1.8),
        "back_knee_bend": _series(148, 12.0, 0.6, 2.1),
        "trunk_lateral_flexion": _series(joint["trunk_lateral_flexion_deg"], 6.0, 0.0, 1.5),
        "pelvis_shoulder_separation": _series(38, 8.0, 0.3, 2.4),
        "wrist_trajectory": [
            {
                "frame": i,
                "timestamp": round(i / fps, 3),
                "x": round(50 + 30 * (i / total_frames) + random.uniform(-2, 2), 2),
                "y": round(
                    40 + 45 * math.sin(math.pi * min(i / (release_idx + 1), 1.0))
                    + random.uniform(-1.5, 1.5),
                    2,
                ),
            }
            for i in range(total_frames)
        ],
        "symmetry": [
            {
                "frame": i,
                "timestamp": round(i / fps, 3),
                "left": round(155 + 6 * math.sin(i / 15) + random.uniform(-2, 2), 2),
                "right": round(152 + 7 * math.sin(i / 14) + random.uniform(-2, 2), 2),
            }
            for i in range(total_frames)
        ],
        "risk_heatmap": [
            {
                "frame": i,
                "timestamp": round(i / fps, 3),
                "trunk_flex": round(
                    joint["trunk_lateral_flexion_deg"]
                    + 8 * math.sin(math.pi * (i / total_frames))
                    + random.uniform(-1, 1),
                    2,
                ),
                "band": (
                    "high"
                    if joint["trunk_lateral_flexion_deg"] + 8 * math.sin(math.pi * (i / total_frames)) >= 30
                    else "moderate"
                    if joint["trunk_lateral_flexion_deg"] + 8 * math.sin(math.pi * (i / total_frames)) >= 22
                    else "low"
                ),
            }
            for i in range(total_frames)
        ],
    }

    def _box(values: list[float]) -> dict:
        vs = sorted(values)
        n = len(vs)
        return {
            "min": round(min(vs), 2),
            "q1": round(vs[n // 4], 2),
            "median": round(vs[n // 2], 2),
            "q3": round(vs[(3 * n) // 4], 2),
            "max": round(max(vs), 2),
            "mean": round(sum(vs) / n, 2),
        }

    distribution_stats = {
        "shoulder_alignment": _box([p["value"] for p in motion_series["shoulder_alignment"]]),
        "pelvis_shoulder_separation": _box(
            [p["value"] for p in motion_series["pelvis_shoulder_separation"]]
        ),
        "trunk_lateral_flexion": _box([p["value"] for p in motion_series["trunk_lateral_flexion"]]),
        "front_knee_bend": _box([p["value"] for p in motion_series["front_knee_bend"]]),
    }

    classification = {
        "action_type": "semi_open",
        "action_label": "Semi-open",
        "confidence": 82.0,
        "shoulder_at_bfc_deg": round(_jitter(18.0, 0.15), 1),
        "shoulder_at_ffc_deg": round(_jitter(24.0, 0.1), 1),
        "shoulder_delta_deg": 6.0,
        "description": (
            "Demo profile — intermediate shoulder alignment between side-on and front-on, "
            "commonly seen in rhythm seamers."
        ),
    }

    injury_analysis = {
        "probability": 22.0,
        "band": "Low",
        "contributors": [
            {"label": "Trunk lateral flexion elevated", "weight": 12},
            {"label": "L/R kinematic asymmetry (mild)", "weight": 6},
        ],
    }

    injury_risk = [
        {
            "label": "Lumbar Stress",
            "level": "Moderate",
            "detail": "Based on trunk lateral flexion at ball release (Portus et al. threshold ~30°).",
        },
        {
            "label": "Front Knee Load",
            "level": "Low",
            "detail": f"Estimated peak vGRF of {joint['vGRF_body_weights']} body-weights at FFC.",
        },
        {
            "label": "Shoulder Alignment Drift",
            "level": "Low",
            "detail": "Average shoulder line deviation from horizontal across the run-up.",
        },
        {
            "label": "Mixed-action Flag",
            "level": "Low",
            "detail": "Semi-open action, no counter-rotation flagged.",
        },
        {
            "label": "Front Knee Hyperextension",
            "level": "Low",
            "detail": f"Front knee extension {joint['front_knee_flexion_br_deg']}° at release.",
        },
        {
            "label": "Landing Mechanics",
            "level": "Low",
            "detail": "Stable COM in the 0.15s window after front-foot plant.",
        },
        {
            "label": "Kinematic Asymmetry",
            "level": "Moderate",
            "detail": "Mild L/R asymmetry — expected in demo profile.",
        },
    ]

    coaching_tips = [
        {
            "title": "Deepen pelvis-shoulder separation",
            "detail": "Target 35-45° of separation at release by delaying shoulder rotation after front-foot plant.",
            "severity": "medium",
        },
        {
            "title": "Lock the front leg earlier",
            "detail": "Aim to reach >170° of front-knee extension at release to improve energy transfer.",
            "severity": "low",
        },
        {
            "title": "Trim lateral trunk tilt",
            "detail": "Keep lateral trunk tilt under 22° at release to protect the lumbar spine.",
            "severity": "medium",
        },
    ]

    comparison_metrics = [
        {"metric": "Release Angle", "athlete": joint["release_angle_deg"], "benchmark": 12.0,
         "delta": round(joint["release_angle_deg"] - 12.0, 2), "unit": "deg"},
        {"metric": "Front Leg Brace", "athlete": joint["front_knee_flexion_br_deg"], "benchmark": 170.0,
         "delta": round(joint["front_knee_flexion_br_deg"] - 170.0, 2), "unit": "deg"},
        {"metric": "Pelvis-Shoulder Separation", "athlete": joint["pelvis_shoulder_separation_deg"],
         "benchmark": 42.0,
         "delta": round(joint["pelvis_shoulder_separation_deg"] - 42.0, 2), "unit": "deg"},
        {"metric": "Stride Length", "athlete": joint["stride_length_m"], "benchmark": 1.85,
         "delta": round(joint["stride_length_m"] - 1.85, 2), "unit": "m"},
    ]

    comparison_inputs = {
        "release_angle": joint["release_angle_deg"],
        "front_knee_brace": joint["front_knee_flexion_br_deg"],
        "back_leg_drive": 82.0,
        "shoulder_alignment": 88.0,
        "hip_rotation": joint["pelvis_shoulder_separation_deg"],
        "bowling_arm_speed": 85.0,
        "elbow_extension": 167.0,
        "head_stability": 87.0,
        "follow_through_balance": 82.0,
        "stride_length": joint["stride_length_m"],
        "runup_consistency": 85.0,
        "overall_efficiency": 83.0,
    }

    summary = {
        "overall_score": 78.4,
        "efficiency_score": 81.3,
        "balance_score": 77.2,
        "consistency_score": 79.0,
        "motion_smoothness_score": 72.5,
        "approx_speed_kph": joint["release_speed_kph"],
    }

    return {
        "video_meta": {
            "fps": fps,
            "total_frames": total_frames,
            "analyzed_frames": total_frames,
            "width": 1280,
            "height": 720,
            "bowling_arm": "right",
        },
        "is_demo": True,
        "joint_metrics": joint,
        "classification": classification,
        "injury_analysis": injury_analysis,
        "injury_risk": injury_risk,
        "timing_metrics": {
            "delivery_duration_s": round(total_frames / fps, 2),
            "ffc_to_release_ms": round((release_idx - ffc_idx) / fps * 1000.0, 1),
            "release_frame": release_idx,
            "release_time_s": round(release_idx / fps, 3),
            "front_foot_landing_frame": ffc_idx,
            "front_foot_landing_time_s": round(ffc_idx / fps, 3),
        },
        "scores": {
            "shoulder_alignment": 82.0,
            "pelvis_shoulder_separation": 76.0,
            "trunk_lateral_flexion": 74.0,
            "front_knee_at_ffc": 80.0,
            "front_knee_at_release": 84.0,
            "release_angle": 78.0,
            "release_speed": 81.0,
            "runup_speed": 85.0,
            "stride_length": 88.0,
            "follow_through_balance": 82.0,
            "runup_consistency": 85.0,
            "vGRF": 72.0,
        },
        "comparison_inputs": comparison_inputs,
        "comparison_metrics": comparison_metrics,
        "technique_cards": [
            {"label": "Front Knee at Release", "score": 84, "status": "Elite",
             "insight": f"{joint['front_knee_flexion_br_deg']}° at ball release — locked brace."},
            {"label": "Pelvis-Shoulder Separation", "score": 76, "status": "Strong",
             "insight": f"{joint['pelvis_shoulder_separation_deg']}° of torso wind-up at release."},
            {"label": "Trunk Lateral Flexion", "score": 74, "status": "Strong",
             "insight": f"{joint['trunk_lateral_flexion_deg']}° sideways tilt at release."},
        ],
        "frame_events": [
            {"frame": bfc_idx, "timestamp": round(bfc_idx / fps, 3),
             "label": "Back Foot Contact", "confidence": 0.78},
            {"frame": ffc_idx, "timestamp": round(ffc_idx / fps, 3),
             "label": "Front Foot Contact", "confidence": 0.86},
            {"frame": release_idx, "timestamp": round(release_idx / fps, 3),
             "label": "Ball Release", "confidence": 0.9},
            {"frame": follow_idx, "timestamp": round(follow_idx / fps, 3),
             "label": "Follow Through", "confidence": 0.75},
        ],
        "motion_series": motion_series,
        "distribution_stats": distribution_stats,
        "good_points": [
            "Pelvis-shoulder separation is close to the elite 35-45° window.",
            "Front leg braces well through release.",
            "Run-up rhythm stays consistent across the approach.",
        ],
        "errors_detected": [
            "Trunk lateral flexion is slightly high — watch the sideways tilt at release.",
        ],
        "coaching_tips": coaching_tips,
        "estimation_notes": [
            "DEMO MODE — these metrics are synthetic reference values for platform exploration.",
            "Real uploads use MediaPipe pose on your own footage.",
        ],
        "summary": summary,
    }
