from __future__ import annotations

import math
from typing import Iterable


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def safe_mean(values: Iterable[float], default: float = 0.0) -> float:
    values = list(values)
    if not values:
        return default
    return sum(values) / len(values)


def point_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.dist(a, b)


def angle_between_points(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    ab = (a[0] - b[0], a[1] - b[1])
    cb = (c[0] - b[0], c[1] - b[1])
    dot = ab[0] * cb[0] + ab[1] * cb[1]
    mag_ab = math.hypot(*ab)
    mag_cb = math.hypot(*cb)
    if mag_ab == 0 or mag_cb == 0:
        return 0.0
    cos_angle = clamp(dot / (mag_ab * mag_cb), -1.0, 1.0)
    return math.degrees(math.acos(cos_angle))


def line_angle_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Angle of the vector a->b measured from the positive x-axis in image space.

    Returns value in (-180, 180].
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.degrees(math.atan2(dy, dx))


def lateral_flexion_deg(upper: tuple[float, float], lower: tuple[float, float]) -> float:
    """Trunk lateral flexion: angle of trunk vector relative to vertical axis (in degrees).

    0 = perfectly upright (vertical), positive = lateral tilt magnitude.
    """
    dx = upper[0] - lower[0]
    dy = upper[1] - lower[1]
    # Flip dy since image y grows downward; we want vertical reference upward.
    return math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))


def normalize_score(value: float, ideal: float, tolerance: float) -> float:
    if tolerance == 0:
        return 100.0 if value == ideal else 0.0
    delta = abs(value - ideal)
    ratio = clamp(1 - (delta / tolerance), 0.0, 1.0)
    return ratio * 100
