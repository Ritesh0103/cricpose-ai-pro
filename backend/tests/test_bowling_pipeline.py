from app.pipeline.biomechanics import build_reference_model, compare_to_reference, extract_bowling_features


def _frame(y_wrist: float, knee_y: float = 0.72) -> dict:
    def kp(x, y):
        return {"x": x, "y": y, "z": 0.0, "visibility": 0.95}

    return {
        "keypoints": {
            "left_shoulder": kp(0.42, 0.32),
            "right_shoulder": kp(0.58, 0.32),
            "left_elbow": kp(0.37, 0.2),
            "right_elbow": kp(0.63, 0.24),
            "left_wrist": kp(0.34, y_wrist),
            "right_wrist": kp(0.66, 0.38),
            "left_hip": kp(0.44, 0.58),
            "right_hip": kp(0.56, 0.58),
            "left_knee": kp(0.43, knee_y),
            "right_knee": kp(0.57, 0.74),
            "left_ankle": kp(0.42, 0.92),
            "right_ankle": kp(0.58, 0.92),
        }
    }


def test_extract_reference_and_compare(tmp_path):
    payload = {"detections": [_frame(0.28), _frame(0.12), _frame(0.24)]}

    features = extract_bowling_features(payload, assumed_fps=8.0)
    reference = build_reference_model([features, {**features, "arm_angle_deg": features["arm_angle_deg"] + 2}], tmp_path / "reference.json")
    comparison = compare_to_reference({**features, "knee_bend_deg": features["knee_bend_deg"] + 18}, reference)

    assert features["bowling_side"] == "left"
    assert "release_angle_deg" in features
    assert reference["sample_count"] == 2
    assert comparison["score"] <= 100
    assert comparison["feedback"]
