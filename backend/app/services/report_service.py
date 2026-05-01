from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException

from app.core.db import get_db


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid report id") from exc


async def insert_report(
    *,
    user_id: ObjectId,
    title: str,
    source_path: str,
    processed_path: Optional[str],
    tracking_path: Optional[str],
    sidebyside_path: Optional[str],
    slowmo_path: Optional[str],
    thumbnail_path: Optional[str],
    summary: dict,
    metrics: dict,
    status: str = "done",
    error: Optional[str] = None,
) -> dict:
    doc = {
        "user_id": user_id,
        "title": title,
        "source_video_path": source_path,
        "processed_video_path": processed_path,
        "tracking_video_path": tracking_path,
        "sidebyside_video_path": sidebyside_path,
        "slowmo_video_path": slowmo_path,
        "thumbnail_path": thumbnail_path,
        "pdf_report_path": None,
        "overall_score": summary.get("overall_score", 0.0),
        "efficiency_score": summary.get("efficiency_score", 0.0),
        "balance_score": summary.get("balance_score", 0.0),
        "consistency_score": summary.get("consistency_score", 0.0),
        "motion_smoothness_score": summary.get("motion_smoothness_score", 0.0),
        "approx_speed_kph": summary.get("approx_speed_kph", 0.0),
        "metrics": metrics,
        "created_at": datetime.now(timezone.utc),
        "status": status,
        "error": error,
    }
    result = await get_db().reports.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def update_processing_result(
    report_id: ObjectId,
    *,
    status: str,
    processed_path: Optional[str] = None,
    tracking_path: Optional[str] = None,
    sidebyside_path: Optional[str] = None,
    slowmo_path: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
    summary: Optional[dict] = None,
    metrics: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    update: dict = {"status": status, "error": error}
    if summary is not None:
        update["overall_score"] = summary.get("overall_score", 0.0)
        update["efficiency_score"] = summary.get("efficiency_score", 0.0)
        update["balance_score"] = summary.get("balance_score", 0.0)
        update["consistency_score"] = summary.get("consistency_score", 0.0)
        update["motion_smoothness_score"] = summary.get("motion_smoothness_score", 0.0)
        update["approx_speed_kph"] = summary.get("approx_speed_kph", 0.0)
    if metrics is not None:
        update["metrics"] = metrics
    if processed_path is not None:
        update["processed_video_path"] = processed_path
    if tracking_path is not None:
        update["tracking_video_path"] = tracking_path
    if sidebyside_path is not None:
        update["sidebyside_video_path"] = sidebyside_path
    if slowmo_path is not None:
        update["slowmo_video_path"] = slowmo_path
    if thumbnail_path is not None:
        update["thumbnail_path"] = thumbnail_path
    await get_db().reports.update_one({"_id": report_id}, {"$set": update})


async def set_pdf_path(report_id: ObjectId, pdf_path: str) -> None:
    await get_db().reports.update_one({"_id": report_id}, {"$set": {"pdf_report_path": pdf_path}})


async def get_report(report_id: str, user_id: ObjectId) -> dict:
    db = get_db()
    report = await db.reports.find_one({"_id": _oid(report_id), "user_id": user_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


async def list_reports(user_id: ObjectId) -> list[dict]:
    cursor = get_db().reports.find({"user_id": user_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def dashboard_summary(user_id: ObjectId) -> dict:
    db = get_db()
    total = await db.reports.count_documents({"user_id": user_id})
    cursor = db.reports.find({"user_id": user_id}).sort("created_at", -1).limit(50)
    reports = [doc async for doc in cursor]
    avg = round(sum(r.get("overall_score", 0) for r in reports) / len(reports), 1) if reports else 0.0
    best = round(max((r.get("overall_score", 0) for r in reports), default=0.0), 1)
    recent = [
        {
            "id": str(r["_id"]),
            "title": r.get("title", "Bowling Analysis"),
            "created_at": r["created_at"].isoformat(),
            "overall_score": r.get("overall_score", 0),
        }
        for r in reports[:5]
    ]
    # Chronological trend for the progress chart (oldest first, up to 15 points).
    trend_reports = list(reversed(reports[:15]))
    score_trend = [
        {
            "date": r["created_at"].strftime("%b %d"),
            "timestamp": r["created_at"].isoformat(),
            "overall_score": round(r.get("overall_score", 0), 1),
            "efficiency_score": round(r.get("efficiency_score", 0), 1),
            "release_speed_kph": round(r.get("approx_speed_kph", 0), 1),
            "injury_probability": round(
                (r.get("metrics", {}) or {}).get("injury_analysis", {}).get("probability", 0),
                1,
            ),
        }
        for r in trend_reports
    ]
    latest = None
    if reports:
        top = reports[0]
        j = (top.get("metrics", {}) or {}).get("joint_metrics", {})
        inj = (top.get("metrics", {}) or {}).get("injury_analysis", {})
        cls = (top.get("metrics", {}) or {}).get("classification", {})
        latest = {
            "id": str(top["_id"]),
            "title": top.get("title", "Bowling Analysis"),
            "created_at": top["created_at"].isoformat(),
            "overall_score": round(top.get("overall_score", 0), 1),
            "release_speed_kph": j.get("release_speed_kph", top.get("approx_speed_kph", 0)),
            "injury_probability": inj.get("probability", 0),
            "injury_band": inj.get("band", "Low"),
            "action_label": cls.get("action_label", "—"),
        }
    return {
        "total_reports": total,
        "average_overall_score": avg,
        "best_score": best,
        "recent_activity": recent,
        "score_trend": score_trend,
        "latest": latest,
    }


def to_response(report: dict) -> dict:
    rid = str(report["_id"])
    source_url = f"/api/analysis/{rid}/source" if report.get("source_video_path") else None
    processed_url = f"/api/analysis/{rid}/video" if report.get("processed_video_path") else None
    tracking_url = f"/api/analysis/{rid}/tracking" if report.get("tracking_video_path") else None
    sbs_url = f"/api/analysis/{rid}/sidebyside" if report.get("sidebyside_video_path") else None
    slowmo_url = f"/api/analysis/{rid}/slowmo" if report.get("slowmo_video_path") else None
    thumb_url = f"/api/analysis/{rid}/thumbnail" if report.get("thumbnail_path") else None
    pdf_url = f"/api/reports/{rid}/pdf" if report.get("pdf_report_path") else None
    return {
        "id": rid,
        "title": report.get("title", "Bowling Analysis"),
        "created_at": report.get("created_at"),
        "overall_score": report.get("overall_score", 0.0),
        "efficiency_score": report.get("efficiency_score", 0.0),
        "balance_score": report.get("balance_score", 0.0),
        "consistency_score": report.get("consistency_score", 0.0),
        "motion_smoothness_score": report.get("motion_smoothness_score", 0.0),
        "approx_speed_kph": report.get("approx_speed_kph", 0.0),
        "score": report.get("overall_score", 0.0),
        "status": report.get("status", "done"),
        "error": report.get("error"),
        "original_video_path": source_url,
        "processed_video_path": processed_url,
        "thumbnail_path": thumb_url,
        "source_video_url": source_url,
        "processed_video_url": processed_url,
        "tracking_video_url": tracking_url,
        "sidebyside_video_url": sbs_url,
        "slowmo_video_url": slowmo_url,
        "thumbnail_url": thumb_url,
        "pdf_report_url": pdf_url,
        "metrics": report.get("metrics", {}),
    }
