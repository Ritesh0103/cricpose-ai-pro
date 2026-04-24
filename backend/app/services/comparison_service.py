from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from app.models import CompareMetricResponse, CompareResponse, CompareTargetProfile, CompareVisuals
from app.utils.geometry import clamp

METRIC_META = {
    "release_angle": {"label": "Release Angle", "unit": "deg", "weight": 0.11, "tolerance": 14.0},
    "front_knee_brace": {"label": "Front Knee Brace", "unit": "deg", "weight": 0.1, "tolerance": 14.0},
    "back_leg_drive": {"label": "Back Leg Drive", "unit": "score", "weight": 0.08, "tolerance": 12.0},
    "shoulder_alignment": {"label": "Shoulder Alignment", "unit": "score", "weight": 0.1, "tolerance": 10.0},
    "hip_rotation": {"label": "Pelvis-Shoulder Sep.", "unit": "deg", "weight": 0.1, "tolerance": 14.0},
    "bowling_arm_speed": {"label": "Release Speed Score", "unit": "score", "weight": 0.1, "tolerance": 12.0},
    "elbow_extension": {"label": "Elbow Extension", "unit": "deg", "weight": 0.08, "tolerance": 10.0},
    "head_stability": {"label": "Head Stability", "unit": "score", "weight": 0.08, "tolerance": 10.0},
    "follow_through_balance": {"label": "Follow-through Balance", "unit": "score", "weight": 0.08, "tolerance": 12.0},
    "stride_length": {"label": "Stride Length", "unit": "m", "weight": 0.06, "tolerance": 0.22},
    "runup_consistency": {"label": "Run-up Consistency", "unit": "score", "weight": 0.05, "tolerance": 10.0},
    "overall_efficiency": {"label": "Overall Efficiency", "unit": "score", "weight": 0.06, "tolerance": 10.0},
}

GROUP_TAGS = {"closest": None, "pace_legends": "pace", "swing_bowlers": "swing", "sling_actions": "sling", "custom": None}


@lru_cache(maxsize=1)
def load_profiles() -> list[dict]:
    data_path = Path(__file__).resolve().parents[1] / "data" / "elite_bowler_profiles.json"
    return json.loads(data_path.read_text(encoding="utf-8"))


def list_profiles() -> list[CompareTargetProfile]:
    return [_profile_summary(p) for p in load_profiles()]


def compare_analysis(
    *,
    report: dict,
    target_bowler: str | None,
    comparison_group: str | None,
) -> CompareResponse:
    profiles = load_profiles()
    candidates = _select_profiles(profiles, target_bowler, comparison_group)
    if not candidates:
        raise HTTPException(status_code=404, detail="No comparison profiles available")

    athlete = _extract_athlete_metrics(report.get("metrics", {}))
    scored = [(profile, _score_profile_similarity(athlete, profile["metrics"])) for profile in candidates]
    best_profile, similarity = max(scored, key=lambda item: item[1])

    compared_metrics = _build_metric_rows(athlete, best_profile["metrics"])
    strengths = [row.insight for row in compared_metrics if row.status == "better"][:4]
    weaknesses = [row.insight for row in compared_metrics if row.status == "needs-work"][:4]
    coaching_tips = _build_coaching_tips(compared_metrics, best_profile)

    return CompareResponse(
        analysis_id=str(report["_id"]),
        best_match=_profile_summary(best_profile),
        similarity_score=round(similarity, 1),
        comparison_group=comparison_group or "closest",
        compared_metrics=compared_metrics,
        strengths=strengths,
        weaknesses=weaknesses,
        coaching_tips=coaching_tips,
        visuals=CompareVisuals(
            user_video_url=f"/api/analysis/{report['_id']}/source",
            processed_video_url=f"/api/analysis/{report['_id']}/video" if report.get("processed_video_path") else None,
            reference_label=best_profile["visual"]["label"],
            reference_style=best_profile["visual"]["stance"],
            reference_palette=[best_profile["visual"]["primary"], best_profile["visual"]["secondary"]],
        ),
        available_profiles=[_profile_summary(p) for p in profiles],
    )


def _select_profiles(profiles: list[dict], target_bowler: str | None, comparison_group: str | None) -> list[dict]:
    if target_bowler:
        return [p for p in profiles if p["name"] == target_bowler]
    tag = GROUP_TAGS.get((comparison_group or "closest").lower())
    if not tag:
        return list(profiles)
    return [p for p in profiles if tag in p["tags"]]


def _extract_athlete_metrics(metrics: dict) -> dict[str, float]:
    inputs = metrics.get("comparison_inputs", {})
    if inputs:
        return {k: float(v) for k, v in inputs.items() if k in METRIC_META}
    return {k: 0.0 for k in METRIC_META}


def _score_profile_similarity(athlete: dict[str, float], benchmark: dict[str, float]) -> float:
    weighted = 0.0
    total_w = 0.0
    for key, meta in METRIC_META.items():
        a = athlete.get(key, 0.0)
        b = benchmark.get(key, 0.0)
        sim = clamp(100 - (abs(a - b) / meta["tolerance"]) * 100, 0, 100)
        weighted += sim * meta["weight"]
        total_w += meta["weight"]
    return weighted / total_w if total_w else 0.0


def _build_metric_rows(athlete: dict[str, float], benchmark: dict[str, float]) -> list[CompareMetricResponse]:
    rows: list[CompareMetricResponse] = []
    for key, meta in METRIC_META.items():
        a = athlete.get(key, 0.0)
        b = benchmark.get(key, 0.0)
        delta = a - b
        pct = 0.0 if b == 0 else (delta / b) * 100
        sim = clamp(100 - (abs(delta) / meta["tolerance"]) * 100, 0, 100)
        status = "elite-benchmark"
        if sim < 70:
            status = "needs-work"
        elif delta >= 0:
            status = "better"
        rows.append(
            CompareMetricResponse(
                key=key,
                label=meta["label"],
                unit=meta["unit"],
                athlete_value=round(a, 2),
                benchmark_value=round(b, 2),
                delta=round(delta, 2),
                delta_percent=round(pct, 1),
                weight=meta["weight"],
                similarity=round(sim, 1),
                status=status,
                insight=_metric_insight(meta["label"], delta, pct),
            )
        )
    return rows


def _metric_insight(label: str, delta: float, pct_gap: float) -> str:
    if abs(pct_gap) < 4:
        return f"{label} is tracking close to elite benchmark levels."
    if delta > 0:
        return f"{label} is outperforming the selected benchmark by {abs(pct_gap):.1f}%."
    return f"{label} trails the selected benchmark by {abs(pct_gap):.1f}%."


def _build_coaching_tips(metrics: list[CompareMetricResponse], profile: dict) -> list[str]:
    sorted_metrics = sorted(metrics, key=lambda m: m.similarity)
    weakest = sorted_metrics[:3]
    tips: list[str] = []
    for m in weakest:
        if m.key == "front_knee_brace":
            tips.append(f"Front knee brace is {abs(m.delta_percent):.1f}% weaker than {profile['name']}; lock the leg earlier.")
        elif m.key == "hip_rotation":
            tips.append("Deepen pelvis-shoulder separation — delay upper-body rotation after front foot contact.")
        elif m.key == "bowling_arm_speed":
            tips.append("Raise arm acceleration after gather without compromising alignment to lift release speed.")
        elif m.key == "stride_length":
            tips.append("Stride length is off the elite band — work on approach rhythm and final bound.")
        else:
            tips.append(m.insight)
    return tips[:4]


def _profile_summary(profile: dict) -> CompareTargetProfile:
    return CompareTargetProfile(
        name=profile["name"],
        style=profile["style"],
        handedness=profile["handedness"],
        speed_range=profile["speed_range"],
        archetype=profile["archetype"],
        metrics=profile["metrics"],
        tags=profile["tags"],
        visual=profile["visual"],
    )
