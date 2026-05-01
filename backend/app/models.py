from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: str
    full_name: str
    email: str
    role: str = "athlete"
    created_at: datetime


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ReportSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    overall_score: float
    efficiency_score: float


class DashboardSummary(BaseModel):
    total_reports: int
    average_overall_score: float
    best_score: float
    recent_activity: list[dict]
    score_trend: list[dict] = []
    latest: Optional[dict] = None


class AnalysisResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    overall_score: float
    efficiency_score: float
    balance_score: float
    consistency_score: float
    motion_smoothness_score: float
    approx_speed_kph: float
    score: float
    status: str = "done"
    error: Optional[str] = None
    original_video_path: Optional[str] = None
    processed_video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    source_video_url: Optional[str] = None
    processed_video_url: Optional[str] = None
    tracking_video_url: Optional[str] = None
    sidebyside_video_url: Optional[str] = None
    slowmo_video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    pdf_report_url: Optional[str] = None
    metrics: dict


class AnalysisJobStatus(BaseModel):
    id: str
    status: str  # processing | done | failed
    error: Optional[str] = None


class CompareRequest(BaseModel):
    analysis_id: str
    target_bowler: Optional[str] = None
    comparison_group: Optional[str] = "closest"


class CompareMetricResponse(BaseModel):
    key: str
    label: str
    unit: str
    athlete_value: float
    benchmark_value: float
    delta: float
    delta_percent: float
    weight: float
    similarity: float
    status: str
    insight: str


class CompareVisuals(BaseModel):
    user_video_url: str
    processed_video_url: Optional[str] = None
    reference_label: str
    reference_style: str
    reference_palette: list[str]


class CompareTargetProfile(BaseModel):
    name: str
    style: str
    handedness: str
    speed_range: list[int]
    archetype: str
    metrics: dict[str, float]
    tags: list[str]
    visual: dict[str, str]


class CompareResponse(BaseModel):
    analysis_id: str
    best_match: CompareTargetProfile
    similarity_score: float
    comparison_group: str
    compared_metrics: list[CompareMetricResponse]
    strengths: list[str]
    weaknesses: list[str]
    coaching_tips: list[str]
    visuals: CompareVisuals
    available_profiles: list[CompareTargetProfile]


def user_to_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        full_name=doc.get("full_name") or doc.get("name") or "Athlete",
        email=doc["email"],
        role=doc.get("role", "athlete"),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
    )
