from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf(destination: Path, athlete_name: str, report: dict) -> Path:
    doc = SimpleDocTemplate(str(destination), pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], textColor=colors.HexColor("#57f0ff"), fontSize=24, leading=28)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, textColor=colors.HexColor("#223041"), leading=14)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=15, textColor=colors.HexColor("#062233"))

    created = report.get("created_at", datetime.utcnow())
    if isinstance(created, str):
        date_str = created
    else:
        date_str = created.strftime("%Y-%m-%d %H:%M")

    metrics = report.get("metrics", {})
    summary = metrics.get("summary", {})
    joint = metrics.get("joint_metrics", {})

    elements = [
        Paragraph("CricPose AI Pro — Biomechanics Report", title_style),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>Athlete:</b> {athlete_name}", body_style),
        Paragraph(f"<b>Date:</b> {date_str}", body_style),
        Spacer(1, 6 * mm),
        Paragraph("Performance Snapshot", section_style),
        Spacer(1, 4 * mm),
    ]

    score_table = Table([
        ["Overall", "Efficiency", "Balance", "Consistency", "Smoothness", "Release Speed"],
        [
            f"{summary.get('overall_score', 0):.1f}/100",
            f"{summary.get('efficiency_score', 0):.1f}",
            f"{summary.get('balance_score', 0):.1f}",
            f"{summary.get('consistency_score', 0):.1f}",
            f"{summary.get('motion_smoothness_score', 0):.1f}",
            f"{summary.get('approx_speed_kph', 0):.1f} kph",
        ],
    ])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#062233")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#e7f4fb")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#062233")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b5d4e3")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.extend([score_table, Spacer(1, 6 * mm), Paragraph("Joint Metrics", section_style), Spacer(1, 3 * mm)])

    joint_rows = [["Metric", "Value"]]
    pretty = {
        "release_angle_deg": "Release Angle (deg)",
        "pelvis_shoulder_separation_deg": "Pelvis-Shoulder Separation (deg)",
        "trunk_lateral_flexion_deg": "Trunk Lateral Flexion (deg)",
        "front_knee_flexion_ffc_deg": "Front Knee Flexion @ FFC (deg)",
        "front_knee_flexion_br_deg": "Front Knee Flexion @ Release (deg)",
        "stride_length_m": "Stride Length (m)",
        "runup_speed_kph": "Run-up Speed (kph)",
        "release_speed_kph": "Ball Release Speed (kph)",
        "vGRF_body_weights": "Peak vGRF (body weights)",
    }
    for key, label in pretty.items():
        if key in joint:
            joint_rows.append([label, f"{joint[key]}"])
    metrics_table = Table(joint_rows, colWidths=[90 * mm, 60 * mm])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#062233")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f4faff")),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#062233")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b5d4e3")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.extend([metrics_table, Spacer(1, 6 * mm), Paragraph("Coaching Insights", section_style)])
    for tip in metrics.get("coaching_tips", []):
        elements.append(Paragraph(f"<b>{tip.get('title','')}:</b> {tip.get('detail','')}", body_style))
        elements.append(Spacer(1, 2 * mm))

    elements.extend([Spacer(1, 4 * mm), Paragraph("Detected Positives", section_style)])
    for item in metrics.get("good_points", []):
        elements.append(Paragraph(f"• {item}", body_style))

    elements.extend([Spacer(1, 4 * mm), Paragraph("Improvement Areas", section_style)])
    for item in metrics.get("errors_detected", []):
        elements.append(Paragraph(f"• {item}", body_style))

    doc.build(elements)
    return destination
