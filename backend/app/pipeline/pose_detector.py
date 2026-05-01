from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
logger = logging.getLogger("cricpose.pipeline.pose_detector")

KEYPOINT_LANDMARKS = {
    "left_shoulder": mp_pose.PoseLandmark.LEFT_SHOULDER,
    "right_shoulder": mp_pose.PoseLandmark.RIGHT_SHOULDER,
    "left_elbow": mp_pose.PoseLandmark.LEFT_ELBOW,
    "right_elbow": mp_pose.PoseLandmark.RIGHT_ELBOW,
    "left_wrist": mp_pose.PoseLandmark.LEFT_WRIST,
    "right_wrist": mp_pose.PoseLandmark.RIGHT_WRIST,
    "left_hip": mp_pose.PoseLandmark.LEFT_HIP,
    "right_hip": mp_pose.PoseLandmark.RIGHT_HIP,
    "left_knee": mp_pose.PoseLandmark.LEFT_KNEE,
    "right_knee": mp_pose.PoseLandmark.RIGHT_KNEE,
    "left_ankle": mp_pose.PoseLandmark.LEFT_ANKLE,
    "right_ankle": mp_pose.PoseLandmark.RIGHT_ANKLE,
}


def _center_crop(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    side = min(height, width)
    x1 = max(0, (width - side) // 2)
    y1 = max(0, (height - side) // 2)
    return frame[y1 : y1 + side, x1 : x1 + side]


class PersonCropper:
    """Optional YOLOv8 person cropper with center-crop fallback.

    The pipeline remains production-safe if ultralytics/model download is unavailable:
    it logs once and falls back to deterministic center crops.
    """

    def __init__(self) -> None:
        self._model = None
        self._load_attempted = False
        self._disabled_reason: str | None = None

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            from ultralytics import YOLO  # type: ignore

            self._model = YOLO("yolov8n.pt")
        except Exception as exc:  # pragma: no cover - depends on optional runtime package/network
            self._disabled_reason = str(exc)
            logger.warning("YOLOv8 person crop unavailable; using center crop fallback: %s", exc)

    def crop(self, frame: np.ndarray) -> np.ndarray:
        self._load()
        if self._model is None:
            return _center_crop(frame)
        try:
            results = self._model.predict(frame, classes=[0], verbose=False)
            boxes = results[0].boxes if results else None
            if boxes is None or len(boxes) == 0:
                return _center_crop(frame)
            xyxy = boxes.xyxy.cpu().numpy()
            areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
            x1, y1, x2, y2 = xyxy[int(np.argmax(areas))]
            height, width = frame.shape[:2]
            pad_x = int((x2 - x1) * 0.25)
            pad_y = int((y2 - y1) * 0.25)
            x1 = max(0, int(x1) - pad_x)
            y1 = max(0, int(y1) - pad_y)
            x2 = min(width, int(x2) + pad_x)
            y2 = min(height, int(y2) + pad_y)
            if x2 <= x1 or y2 <= y1:
                return _center_crop(frame)
            return frame[y1:y2, x1:x2]
        except Exception as exc:  # pragma: no cover
            logger.warning("YOLOv8 crop failed; using center crop fallback: %s", exc)
            return _center_crop(frame)


class MediaPipePoseDetector:
    def __init__(
        self,
        *,
        static_image_mode: bool = True,
        model_complexity: int = 1,
        min_visibility: float = 0.5,
    ) -> None:
        self._pose = mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            smooth_landmarks=True,
            min_detection_confidence=0.35,
            min_tracking_confidence=0.35,
        )
        self._min_visibility = min_visibility
        self._cropper = PersonCropper()

    def close(self) -> None:
        self._pose.close()

    def _detect_frame(self, frame: np.ndarray, frame_name: str) -> dict | None:
        frame = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_AREA)
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return None

        keypoints: dict[str, dict] = {}
        visibility_values: list[float] = []
        for name, landmark_id in KEYPOINT_LANDMARKS.items():
            lm = result.pose_landmarks.landmark[landmark_id]
            visibility_values.append(float(lm.visibility))
            keypoints[name] = {
                "x": float(lm.x),
                "y": float(lm.y),
                "z": float(lm.z),
                "visibility": float(lm.visibility),
                "pixel": [int(lm.x * width), int(lm.y * height)],
            }
        if float(np.median(visibility_values)) < self._min_visibility:
            return None
        return {"frame": frame_name, "width": width, "height": height, "keypoints": keypoints}

    def detect_image(self, image_path: Path, *, zoom: bool = False) -> dict | None:
        frame = cv2.imread(str(image_path))
        if frame is None:
            return None
        if zoom:
            frame = self._cropper.crop(frame)
        return self._detect_frame(frame, image_path.name)

    def _run_pass(self, frames: list[Path], *, zoom: bool = False, frame_step: int = 1) -> tuple[list[dict], int]:
        detections = []
        missed = 0
        for image_path in frames[:: max(1, frame_step)]:
            detection = self.detect_image(image_path, zoom=zoom)
            if detection is None:
                missed += 1
                continue
            detections.append(detection)
        return detections, missed

    def process_frame_dir(self, frame_dir: Path, output_json: Path) -> dict:
        frames = sorted(frame_dir.glob("*.jpg"))
        total_frames = len(frames)
        detections, missed = self._run_pass(frames, zoom=False)
        success_ratio = len(detections) / total_frames if total_frames else 0.0

        if len(detections) == 0 or success_ratio < 0.05:
            print("Low pose detection; retrying with YOLO/center zoom crop")
            zoomed, zoom_missed = self._run_pass(frames, zoom=True)
            if len(zoomed) > len(detections):
                detections = zoomed
                missed = zoom_missed
                success_ratio = len(detections) / total_frames if total_frames else 0.0

        if len(detections) == 0:
            lower_fps_step = 2
            print("No pose after zoom retry; retrying sparse lower-FPS frame pass")
            sparse, sparse_missed = self._run_pass(frames, zoom=True, frame_step=lower_fps_step)
            detections = sparse
            missed = sparse_missed + max(0, total_frames - len(frames[::lower_fps_step]))
            success_ratio = len(detections) / total_frames if total_frames else 0.0

        print(
            "Pose detection summary: "
            f"total frames={total_frames}, detected frames={len(detections)}, "
            f"success ratio={success_ratio:.4f}"
        )
        if len(detections) > 0 and success_ratio < 0.05:
            print("Very low detection, but continuing pipeline")

        payload = {
            "source_frames": str(frame_dir),
            "total_frames": total_frames,
            "detected_frames": len(detections),
            "missed_frames": missed,
            "success_ratio": success_ratio,
            "detections": detections,
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload


def draw_pose_overlay(input_video: Path, output_video: Path) -> None:
    """Create an optional skeleton overlay video for frontend review."""
    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {input_video}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, smooth_landmarks=True)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if result.pose_landmarks:
                mp_draw.draw_landmarks(frame, result.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            writer.write(frame)
    finally:
        pose.close()
        cap.release()
        writer.release()
