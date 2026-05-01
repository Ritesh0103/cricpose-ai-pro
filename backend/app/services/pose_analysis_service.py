from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from app.utils.geometry import (
    angle_between_points,
    clamp,
    lateral_flexion_deg,
    normalize_score,
    point_distance,
    safe_mean,
)

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles


@dataclass
class PoseFrame:
    frame_index: int
    timestamp: float
    landmarks: dict[str, tuple[float, float]]
    world_landmarks: dict[str, tuple[float, float, float]]
    visibility: dict[str, float]


class PoseAnalysisService:
    """Research-grade single-camera biomechanics analysis pipeline.

    Implements metrics inspired by fast bowling literature:
    - Shoulder alignment, pelvis-shoulder (hip-shoulder) separation angle
    - Trunk lateral flexion at release
    - Front knee flexion at front-foot contact (FFC) and at ball release (BR)
    - Vertical ground reaction force (vGRF) estimate via COM vertical deceleration
    - Release speed estimate from bowling-wrist tangential velocity
    - Release angle (bowling arm vs vertical)
    - Run-up speed (COM horizontal velocity over pre-FFC window)
    - Stride length (front-back foot distance at FFC, scaled by hip-width proxy)
    - Follow-through balance (COM stability post-release)
    Events are detected using motion-derived signals:
    - FFC: front-ankle vertical velocity sign change to near-zero (ground contact)
    - BR: bowling-wrist peak upward velocity / highest vertical position
    """

    LANDMARK_INDEX = {
        "nose": mp_pose.PoseLandmark.NOSE,
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
        "left_heel": mp_pose.PoseLandmark.LEFT_HEEL,
        "right_heel": mp_pose.PoseLandmark.RIGHT_HEEL,
        "left_foot_index": mp_pose.PoseLandmark.LEFT_FOOT_INDEX,
        "right_foot_index": mp_pose.PoseLandmark.RIGHT_FOOT_INDEX,
    }

    def analyze_video(
        self,
        source_path: Path,
        processed_path: Path,
        thumbnail_path: Path,
        tracking_path: Path | None = None,
        sidebyside_path: Path | None = None,
        slowmo_path: Path | None = None,
    ) -> dict:
        cap = cv2.VideoCapture(str(source_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(processed_path), fourcc, fps, (width, height))
        tracking_writer = (
            cv2.VideoWriter(str(tracking_path), fourcc, fps, (width, height))
            if tracking_path is not None
            else None
        )
        sbs_writer = (
            cv2.VideoWriter(str(sidebyside_path), fourcc, fps, (width * 2, height))
            if sidebyside_path is not None
            else None
        )

        samples: list[PoseFrame] = []
        thumbnail_saved = False
        # Per-joint 2D image-space trails for the tracking overlay.
        trail_points: dict[str, list[tuple[int, int]]] = {
            "shoulder": [],
            "wrist": [],
            "ankle": [],
        }
        max_trail = 45

        pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        try:
            frame_index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if not thumbnail_saved:
                    cv2.imwrite(str(thumbnail_path), frame)
                    thumbnail_saved = True

                original_frame = frame.copy() if (tracking_writer is not None or sbs_writer is not None) else None

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)

                if results.pose_landmarks:
                    mp_draw.draw_landmarks(
                        frame,
                        results.pose_landmarks,
                        mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_draw.DrawingSpec(color=(87, 240, 255), thickness=3, circle_radius=3),
                        connection_drawing_spec=mp_draw.DrawingSpec(color=(134, 255, 159), thickness=2),
                    )
                    world = results.pose_world_landmarks.landmark if results.pose_world_landmarks else None
                    points: dict[str, tuple[float, float]] = {}
                    world_points: dict[str, tuple[float, float, float]] = {}
                    visibility: dict[str, float] = {}
                    for name, idx in self.LANDMARK_INDEX.items():
                        lm = results.pose_landmarks.landmark[idx]
                        points[name] = (lm.x, lm.y)
                        visibility[name] = float(lm.visibility)
                        if world is not None:
                            w = world[idx]
                            world_points[name] = (w.x, w.y, w.z)
                        else:
                            world_points[name] = (lm.x, lm.y, 0.0)
                    samples.append(
                        PoseFrame(
                            frame_index=frame_index,
                            timestamp=frame_index / fps,
                            landmarks=points,
                            world_landmarks=world_points,
                            visibility=visibility,
                        )
                    )

                    # Keep ankle/wrist/shoulder trails on the bowling-arm side when
                    # available. Handedness gets resolved after the full pass, so we
                    # greedily pick the higher wrist of the current frame as the
                    # "bowling" side which is a good per-frame proxy.
                    bowl_side = "right" if points["right_wrist"][1] <= points["left_wrist"][1] else "left"
                    trail_points["shoulder"].append(
                        (int(points[f"{bowl_side}_shoulder"][0] * width), int(points[f"{bowl_side}_shoulder"][1] * height))
                    )
                    trail_points["wrist"].append(
                        (int(points[f"{bowl_side}_wrist"][0] * width), int(points[f"{bowl_side}_wrist"][1] * height))
                    )
                    trail_points["ankle"].append(
                        (int(points[f"{bowl_side}_ankle"][0] * width), int(points[f"{bowl_side}_ankle"][1] * height))
                    )
                    for key in trail_points:
                        if len(trail_points[key]) > max_trail:
                            trail_points[key] = trail_points[key][-max_trail:]

                writer.write(frame)

                # ---- Tracking overlay (joint paths on clean frame) ----
                if tracking_writer is not None and original_frame is not None:
                    tracking_frame = original_frame.copy()
                    self._draw_trails(tracking_frame, trail_points)
                    tracking_writer.write(tracking_frame)

                # ---- Side-by-side (clean original | skeleton overlay) ----
                if sbs_writer is not None and original_frame is not None:
                    self._annotate_label(original_frame, "ORIGINAL", (36, 46))
                    skeleton_annotated = frame.copy()
                    self._annotate_label(skeleton_annotated, "AI SKELETON", (36, 46))
                    combo = np.hstack((original_frame, skeleton_annotated))
                    sbs_writer.write(combo)

                frame_index += 1
        finally:
            pose.close()
            cap.release()
            writer.release()
            if tracking_writer is not None:
                tracking_writer.release()
            if sbs_writer is not None:
                sbs_writer.release()

        if len(samples) < 5:
            raise ValueError("No bowler detected in the uploaded video. Please upload a clearer delivery clip.")

        # ---- Slow-motion around ball release (second pass) ----
        if slowmo_path is not None:
            self._write_slowmo(source_path, slowmo_path, samples, fps, width, height, fourcc)

        return self._build_payload(samples=samples, fps=fps, total_frames=total_frames, width=width, height=height)

    def _draw_trails(self, frame: np.ndarray, trail_points: dict[str, list[tuple[int, int]]]) -> None:
        palette = {
            "shoulder": (87, 240, 255),  # cyan
            "wrist": (134, 255, 159),    # green
            "ankle": (89, 189, 244),     # warm cyan
        }
        for key, points in trail_points.items():
            if len(points) < 2:
                continue
            base_color = palette[key]
            for i in range(1, len(points)):
                alpha = i / len(points)
                color = tuple(int(c * alpha) for c in base_color)
                cv2.line(frame, points[i - 1], points[i], color, 2, cv2.LINE_AA)
            cv2.circle(frame, points[-1], 6, base_color, -1, cv2.LINE_AA)
            cv2.putText(
                frame,
                key.upper(),
                (points[-1][0] + 8, points[-1][1] - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                base_color,
                2,
                cv2.LINE_AA,
            )

    def _annotate_label(self, frame: np.ndarray, text: str, origin: tuple[int, int]) -> None:
        x, y = origin
        cv2.rectangle(frame, (x - 12, y - 26), (x + 220, y + 10), (8, 21, 35), -1)
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (87, 240, 255), 2, cv2.LINE_AA)

    def _write_slowmo(
        self,
        source_path: Path,
        slowmo_path: Path,
        samples: list[PoseFrame],
        fps: float,
        width: int,
        height: int,
        fourcc: int,
    ) -> None:
        if len(samples) < 5:
            return
        # Focus on a window around the ball release.
        bowling_side = self._handedness(samples)
        events = self._detect_events(samples, fps, bowling_side)
        release_idx = events["ball_release"]
        release_frame = samples[release_idx].frame_index
        window_frames = max(int(fps * 1.2), 20)
        start_frame = max(0, release_frame - window_frames)
        end_frame = release_frame + window_frames

        cap = cv2.VideoCapture(str(source_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        # Write at 1/3 real speed (lower FPS playback = slow motion).
        slow_fps = max(6.0, fps / 3.0)
        writer = cv2.VideoWriter(str(slowmo_path), fourcc, slow_fps, (width, height))
        try:
            frame_idx = start_frame
            while frame_idx <= end_frame:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx == release_frame:
                    cv2.putText(
                        frame,
                        "RELEASE",
                        (32, 56),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.1,
                        (87, 240, 255),
                        3,
                        cv2.LINE_AA,
                    )
                writer.write(frame)
                frame_idx += 1
        finally:
            cap.release()
            writer.release()

    # -------------------------------------------------------------------------
    # Core derivations
    # -------------------------------------------------------------------------

    def _handedness(self, samples: list[PoseFrame]) -> str:
        """Infer bowling arm via peak wrist height across the sequence.

        Returns 'right' or 'left' based on which wrist reaches the highest point
        (smallest y in image coords).
        """
        left_min = min(f.landmarks["left_wrist"][1] for f in samples)
        right_min = min(f.landmarks["right_wrist"][1] for f in samples)
        return "right" if right_min < left_min else "left"

    def _detect_events(self, samples: list[PoseFrame], fps: float, bowling_side: str) -> dict[str, int]:
        front_key = "left_ankle" if bowling_side == "right" else "right_ankle"
        wrist_key = "right_wrist" if bowling_side == "right" else "left_wrist"

        front_y = np.array([f.landmarks[front_key][1] for f in samples])
        wrist_y = np.array([f.landmarks[wrist_key][1] for f in samples])

        # Ball release: wrist reaches highest position (minimum y in image coords).
        release_idx = int(np.argmin(wrist_y))

        # Front foot contact: frame before release with sharpest downward
        # acceleration where foot stops descending and stabilizes.
        search_end = max(release_idx, 3)
        search_start = max(0, search_end - max(5, int(fps * 0.6)))
        window = front_y[search_start : search_end + 1]
        if len(window) >= 3:
            dy = np.gradient(window)
            # FFC candidate: first index where vertical velocity drops from
            # positive (descending) to near zero (planted).
            ffc_local = int(np.argmax(window))  # fallback: lowest point in window
            for i in range(1, len(dy)):
                if dy[i - 1] > 0 and abs(dy[i]) < 1e-3:
                    ffc_local = i
                    break
            ffc_idx = int(search_start + ffc_local)
        else:
            ffc_idx = max(0, release_idx - int(fps * 0.15))

        ffc_idx = min(max(0, ffc_idx), len(samples) - 1)
        if ffc_idx >= release_idx:
            ffc_idx = max(0, release_idx - 1)

        # Follow-through: ~0.35s after release
        follow_idx = min(len(samples) - 1, release_idx + max(3, int(fps * 0.35)))

        # Back-foot contact (BFC): the previous time the back ankle reached
        # its lowest point before FFC.
        back_key = "right_ankle" if bowling_side == "right" else "left_ankle"
        back_y = np.array([f.landmarks[back_key][1] for f in samples[: ffc_idx + 1]])
        bfc_idx = int(np.argmax(back_y)) if len(back_y) > 0 else 0

        return {
            "back_foot_contact": bfc_idx,
            "front_foot_contact": ffc_idx,
            "ball_release": release_idx,
            "follow_through": follow_idx,
        }

    def _body_height_proxy(self, samples: list[PoseFrame]) -> float:
        """Normalised 2D body height proxy in image units.

        Uses the median distance between nose and mid-ankle across frames.
        """
        heights: list[float] = []
        for f in samples:
            mid_ankle_y = (f.landmarks["left_ankle"][1] + f.landmarks["right_ankle"][1]) / 2.0
            nose_y = f.landmarks["nose"][1]
            heights.append(abs(mid_ankle_y - nose_y))
        return float(np.median(heights) or 0.5)

    def _center_of_mass(self, f: PoseFrame) -> tuple[float, float]:
        # Approximate COM at mid-hip
        mid_hip_x = (f.landmarks["left_hip"][0] + f.landmarks["right_hip"][0]) / 2.0
        mid_hip_y = (f.landmarks["left_hip"][1] + f.landmarks["right_hip"][1]) / 2.0
        return mid_hip_x, mid_hip_y

    def _pelvis_shoulder_separation(self, f: PoseFrame) -> float:
        """Absolute angle between the shoulder line and the hip line (degrees)."""
        sl = f.landmarks["left_shoulder"]
        sr = f.landmarks["right_shoulder"]
        hl = f.landmarks["left_hip"]
        hr = f.landmarks["right_hip"]
        sh_vec = (sr[0] - sl[0], sr[1] - sl[1])
        hp_vec = (hr[0] - hl[0], hr[1] - hl[1])
        sh_mag = (sh_vec[0] ** 2 + sh_vec[1] ** 2) ** 0.5
        hp_mag = (hp_vec[0] ** 2 + hp_vec[1] ** 2) ** 0.5
        if sh_mag == 0 or hp_mag == 0:
            return 0.0
        cos_angle = (sh_vec[0] * hp_vec[0] + sh_vec[1] * hp_vec[1]) / (sh_mag * hp_mag)
        cos_angle = clamp(cos_angle, -1.0, 1.0)
        return float(abs(np.degrees(np.arccos(cos_angle))))

    def _release_angle_deg(self, f: PoseFrame, bowling_side: str) -> float:
        """Angle between bowling arm (shoulder -> wrist) and vertical axis (degrees)."""
        shoulder = f.landmarks[f"{bowling_side}_shoulder"]
        wrist = f.landmarks[f"{bowling_side}_wrist"]
        dx = wrist[0] - shoulder[0]
        dy = wrist[1] - shoulder[1]
        # 0 = arm straight up (wrist directly above shoulder in image coords dy < 0)
        return float(np.degrees(np.arctan2(abs(dx), -dy + 1e-6)))

    def _build_payload(
        self,
        *,
        samples: list[PoseFrame],
        fps: float,
        total_frames: int,
        width: int,
        height: int,
    ) -> dict:
        bowling_side = self._handedness(samples)
        events = self._detect_events(samples, fps, bowling_side)
        ffc = events["front_foot_contact"]
        release = events["ball_release"]
        follow = events["follow_through"]

        front_key = "left" if bowling_side == "right" else "right"
        back_key = "right" if bowling_side == "right" else "left"

        body_height_img = self._body_height_proxy(samples)
        assumed_body_height_m = 1.82  # heuristic; single-camera estimate
        image_to_m = assumed_body_height_m / max(body_height_img, 1e-3)

        # Frame-level signals
        shoulder_align = []
        trunk_flexion = []
        ps_separation = []
        arm_angle_seq = []
        knee_front_seq = []
        knee_back_seq = []
        com_x = []
        com_y = []
        front_ankle_x = []

        for f in samples:
            lh = f.landmarks["left_hip"]
            rh = f.landmarks["right_hip"]
            ls = f.landmarks["left_shoulder"]
            rs = f.landmarks["right_shoulder"]
            mid_shoulder = ((ls[0] + rs[0]) / 2.0, (ls[1] + rs[1]) / 2.0)
            mid_hip = ((lh[0] + rh[0]) / 2.0, (lh[1] + rh[1]) / 2.0)

            # Shoulder alignment: deviation from horizontal (smaller is better)
            dx = rs[0] - ls[0]
            dy = rs[1] - ls[1]
            shoulder_align.append(abs(float(np.degrees(np.arctan2(dy, dx + 1e-6)))))

            # Trunk lateral flexion: trunk vector vs vertical
            trunk_flexion.append(lateral_flexion_deg(mid_shoulder, mid_hip))

            # Pelvis-shoulder separation
            ps_separation.append(self._pelvis_shoulder_separation(f))

            # Bowling arm angle (release angle proxy per frame)
            arm_angle_seq.append(self._release_angle_deg(f, bowling_side))

            # Knee flexion (interior angle at knee)
            knee_front_seq.append(
                angle_between_points(
                    f.landmarks[f"{front_key}_hip"],
                    f.landmarks[f"{front_key}_knee"],
                    f.landmarks[f"{front_key}_ankle"],
                )
            )
            knee_back_seq.append(
                angle_between_points(
                    f.landmarks[f"{back_key}_hip"],
                    f.landmarks[f"{back_key}_knee"],
                    f.landmarks[f"{back_key}_ankle"],
                )
            )

            cx, cy = self._center_of_mass(f)
            com_x.append(cx)
            com_y.append(cy)
            front_ankle_x.append(f.landmarks[f"{front_key}_ankle"][0])

        shoulder_align_arr = np.asarray(shoulder_align)
        trunk_flex_arr = np.asarray(trunk_flexion)
        ps_sep_arr = np.asarray(ps_separation)
        arm_arr = np.asarray(arm_angle_seq)
        knee_front_arr = np.asarray(knee_front_seq)
        knee_back_arr = np.asarray(knee_back_seq)
        com_x_arr = np.asarray(com_x)
        com_y_arr = np.asarray(com_y)

        # Event-specific metrics
        front_knee_at_ffc = float(knee_front_arr[ffc]) if ffc < len(knee_front_arr) else float(knee_front_arr.mean())
        front_knee_at_release = float(knee_front_arr[release]) if release < len(knee_front_arr) else front_knee_at_ffc
        knee_flexion_change = front_knee_at_ffc - front_knee_at_release  # positive = extending (good brace)

        trunk_flex_at_release = float(trunk_flex_arr[release]) if release < len(trunk_flex_arr) else float(trunk_flex_arr.mean())
        ps_sep_at_release = float(ps_sep_arr[release]) if release < len(ps_sep_arr) else float(ps_sep_arr.mean())
        release_angle = float(arm_arr[release]) if release < len(arm_arr) else float(arm_arr.max())

        # Stride length at FFC (distance between front and back foot, scaled to meters)
        left_ankle_ffc = samples[ffc].landmarks["left_ankle"]
        right_ankle_ffc = samples[ffc].landmarks["right_ankle"]
        stride_img = point_distance(left_ankle_ffc, right_ankle_ffc)
        stride_length_m = float(clamp(stride_img * image_to_m, 1.2, 2.3))

        # Run-up speed estimate: horizontal COM velocity over pre-FFC window
        runup_window = max(int(fps * 0.6), 5)
        pre_ffc_start = max(0, ffc - runup_window)
        if ffc - pre_ffc_start >= 2:
            dx_total_m = abs(com_x_arr[ffc] - com_x_arr[pre_ffc_start]) * image_to_m
            dt = max((ffc - pre_ffc_start) / fps, 1e-3)
            runup_speed_mps = float(dx_total_m / dt)
        else:
            runup_speed_mps = 0.0
        runup_speed_kph = float(clamp(runup_speed_mps * 3.6, 0.0, 32.0))

        # vGRF estimate: COM vertical deceleration around FFC × assumed body mass
        mass_kg = 75.0  # assumed athlete mass
        ffc_window = max(3, int(fps * 0.1))
        y_start = max(0, ffc - ffc_window)
        y_end = min(len(com_y_arr) - 1, ffc + ffc_window)
        if y_end - y_start >= 2:
            y_m = (com_y_arr[y_start : y_end + 1] * image_to_m).astype(float)
            dt = 1.0 / fps
            vel = np.gradient(y_m, dt)
            acc = np.gradient(vel, dt)
            peak_decel = float(np.max(np.abs(acc)))
            # vGRF ≈ m * (g + |a|) normalised to body weight
            vGRF_bw = (9.81 + peak_decel) / 9.81
            vGRF_N = mass_kg * (9.81 + peak_decel)
        else:
            vGRF_bw = 1.0
            vGRF_N = mass_kg * 9.81
        vGRF_bw = float(clamp(vGRF_bw, 1.0, 9.0))
        vGRF_N = float(clamp(vGRF_N, mass_kg * 9.81, 60_000.0))

        # Release speed estimate from wrist tangential velocity at release
        wrist_key = f"{bowling_side}_wrist"
        w_points = np.array([[f.landmarks[wrist_key][0], f.landmarks[wrist_key][1]] for f in samples]) * image_to_m
        release_lo = max(0, release - 2)
        release_hi = min(len(w_points) - 1, release + 2)
        if release_hi > release_lo:
            dv = w_points[release_hi] - w_points[release_lo]
            dt = (release_hi - release_lo) / fps
            wrist_speed_mps = float(np.linalg.norm(dv) / max(dt, 1e-3))
        else:
            wrist_speed_mps = 0.0
        # Empirical scaling: ball release ~ 1.25 * wrist linear speed (accounts for
        # the moment arm from shoulder to ball).
        release_speed_mps = wrist_speed_mps * 1.25
        release_speed_kph = float(clamp(release_speed_mps * 3.6, 60.0, 165.0))

        # Follow-through balance from COM stability after release
        post_release = com_x_arr[release : follow + 1] * image_to_m
        follow_through_balance = float(clamp(100 - float(np.std(post_release)) * 180.0, 0.0, 100.0))

        # Run-up consistency (variance of COM y during run-up)
        runup_consistency = float(clamp(100 - float(np.std(com_y_arr[pre_ffc_start:ffc] * image_to_m)) * 100.0, 0.0, 100.0))

        # ---- Additional premium metrics ------------------------------------
        # Ball release height: vertical distance from bowling wrist at release
        # down to the mean foot position at FFC (metres).
        foot_y_ffc = (
            samples[ffc].landmarks[f"{front_key}_ankle"][1]
            + samples[ffc].landmarks[f"{back_key}_ankle"][1]
        ) / 2.0
        wrist_y_release = samples[release].landmarks[f"{bowling_side}_wrist"][1]
        release_height_m = float(clamp(abs(foot_y_ffc - wrist_y_release) * image_to_m, 1.6, 2.8))

        # Wrist velocity at release (m/s) — unscaled linear speed of the bowling wrist.
        wrist_velocity_mps = float(clamp(wrist_speed_mps, 0.0, 30.0))

        # Hip rotation angular speed (degrees / second) between FFC and release.
        def _hip_angle_deg(f: PoseFrame) -> float:
            lh = f.landmarks["left_hip"]
            rh = f.landmarks["right_hip"]
            return float(np.degrees(np.arctan2(rh[1] - lh[1], rh[0] - lh[0] + 1e-6)))

        hip_ffc_deg = _hip_angle_deg(samples[ffc])
        hip_release_deg = _hip_angle_deg(samples[release])
        hip_dt = max((samples[release].timestamp - samples[ffc].timestamp), 1.0 / fps)
        hip_rotation_speed_dps = float(clamp(abs(hip_release_deg - hip_ffc_deg) / hip_dt, 0.0, 1400.0))

        # Landing balance score: inverse of COM-x variance during the first 0.15s
        # after front-foot contact (stability window).
        landing_end = min(len(com_x_arr) - 1, ffc + max(2, int(fps * 0.15)))
        if landing_end > ffc:
            landing_var_m = float(np.std(com_x_arr[ffc : landing_end + 1] * image_to_m))
            landing_balance_score = float(clamp(100 - landing_var_m * 320.0, 0.0, 100.0))
        else:
            landing_balance_score = 60.0

        # ---- Bowling action classification ---------------------------------
        shoulder_bfc = float(shoulder_align_arr[events["back_foot_contact"]]) if events["back_foot_contact"] < len(shoulder_align_arr) else 0.0
        shoulder_ffc = float(shoulder_align_arr[ffc]) if ffc < len(shoulder_align_arr) else 0.0
        shoulder_delta = shoulder_ffc - shoulder_bfc
        # Portus/Ferdinands classification thresholds:
        #  - side-on  ~ shoulders close to run-up direction at BFC (<10°)
        #  - front-on ~ shoulders rotated >30° at BFC (chest toward batter)
        #  - semi-open between 10-30°
        #  - mixed = shoulders counter-rotate >20° between BFC and FFC
        if abs(shoulder_delta) >= 20 and np.sign(shoulder_delta) != np.sign(shoulder_bfc + 1e-6):
            action_type = "mixed"
        elif shoulder_bfc <= 10:
            action_type = "side_on"
        elif shoulder_bfc >= 30:
            action_type = "front_on"
        else:
            action_type = "semi_open"
        action_confidence = float(clamp(100 - abs(shoulder_delta - 12) * 2.5, 35.0, 99.0))
        action_label_map = {
            "side_on": "Side-on",
            "front_on": "Front-on",
            "semi_open": "Semi-open",
            "mixed": "Mixed action",
        }
        action_description_map = {
            "side_on": "Shoulders aligned with the run-up direction at back-foot contact — classical side-on action, lowest lumbar stress profile.",
            "front_on": "Chest is already facing the batter at back-foot contact — modern front-on action, relies on strong pelvis rotation.",
            "semi_open": "Intermediate shoulder alignment between side-on and front-on, commonly seen in rhythm seamers.",
            "mixed": "Shoulders and hips counter-rotate between BFC and FFC — MIXED ACTION has the highest published lumbar-stress fracture association (Portus et al.).",
        }

        # ---- Kinematic asymmetry (L/R) --------------------------------------
        symmetry_score = float(
            clamp(
                100 - abs(float(knee_front_arr.mean()) - float(knee_back_arr.mean())) * 0.6,
                0.0,
                100.0,
            )
        )

        # ---- Composite injury probability ----------------------------------
        front_knee_hyperextend = front_knee_at_release > 182
        contributors: list[dict] = []
        probability = 0.0
        if trunk_flex_at_release > 30:
            contributors.append({"label": "Trunk lateral flexion >30°", "weight": 25})
            probability += 25
        elif trunk_flex_at_release > 24:
            contributors.append({"label": "Trunk lateral flexion elevated", "weight": 12})
            probability += 12
        if action_type == "mixed":
            contributors.append({"label": "Mixed shoulder-hip action", "weight": 30})
            probability += 30
        if vGRF_bw > 7:
            contributors.append({"label": f"Peak vGRF {vGRF_bw:.1f} BW (>7)", "weight": 18})
            probability += 18
        elif vGRF_bw > 5.5:
            contributors.append({"label": f"Peak vGRF {vGRF_bw:.1f} BW (elevated)", "weight": 10})
            probability += 10
        if front_knee_hyperextend:
            contributors.append({"label": "Front knee hyperextension at release", "weight": 12})
            probability += 12
        if landing_balance_score < 55:
            contributors.append({"label": "Poor landing mechanics", "weight": 10})
            probability += 10
        if symmetry_score < 55:
            contributors.append({"label": "L/R kinematic asymmetry", "weight": 8})
            probability += 8
        injury_probability = float(clamp(probability, 0.0, 100.0))
        injury_band = (
            "High" if injury_probability >= 55 else "Moderate" if injury_probability >= 25 else "Low"
        )

        # Scores (normalised 0-100 against literature-backed ideals)
        shoulder_score = normalize_score(float(shoulder_align_arr.mean()), 0.0, 18.0)
        trunk_score = normalize_score(trunk_flex_at_release, 18.0, 14.0)
        ps_sep_score = normalize_score(ps_sep_at_release, 40.0, 18.0)
        front_knee_ffc_score = normalize_score(front_knee_at_ffc, 150.0, 22.0)
        front_knee_br_score = normalize_score(front_knee_at_release, 170.0, 16.0)
        release_angle_score = normalize_score(release_angle, 12.0, 18.0)
        release_speed_score = normalize_score(release_speed_kph, 138.0, 30.0)
        runup_speed_score = normalize_score(runup_speed_kph, 22.0, 8.0)
        stride_length_score = normalize_score(stride_length_m, 1.85, 0.3)
        follow_balance_score = follow_through_balance
        runup_consistency_score = runup_consistency
        vGRF_score = normalize_score(vGRF_bw, 5.0, 2.5)

        efficiency_score = float(np.mean([
            shoulder_score,
            ps_sep_score,
            front_knee_br_score,
            trunk_score,
            release_angle_score,
        ]))
        balance_score = float(np.mean([follow_balance_score, trunk_score, shoulder_score]))
        consistency_score = float(np.mean([runup_consistency_score, stride_length_score, runup_speed_score]))
        smoothness = float(clamp(100.0 - float(np.std(np.diff(arm_arr))) * 2.0, 0.0, 100.0)) if len(arm_arr) > 1 else 60.0
        overall_score = round(float(np.mean([efficiency_score, balance_score, consistency_score, smoothness])), 1)

        frame_events = [
            {
                "frame": int(samples[events["back_foot_contact"]].frame_index),
                "timestamp": round(samples[events["back_foot_contact"]].timestamp, 3),
                "label": "Back Foot Contact",
                "confidence": 0.78,
            },
            {
                "frame": int(samples[ffc].frame_index),
                "timestamp": round(samples[ffc].timestamp, 3),
                "label": "Front Foot Contact",
                "confidence": 0.86,
            },
            {
                "frame": int(samples[release].frame_index),
                "timestamp": round(samples[release].timestamp, 3),
                "label": "Ball Release",
                "confidence": 0.9,
            },
            {
                "frame": int(samples[follow].frame_index),
                "timestamp": round(samples[follow].timestamp, 3),
                "label": "Follow Through",
                "confidence": 0.75,
            },
        ]

        def _series(values: np.ndarray, label: str) -> list[dict]:
            return [
                {
                    "frame": samples[i].frame_index,
                    "timestamp": round(samples[i].timestamp, 3),
                    "label": label,
                    "value": round(float(values[i]), 2),
                }
                for i in range(len(values))
            ]

        def _boxplot(values: np.ndarray) -> dict:
            if len(values) == 0:
                return {"min": 0.0, "q1": 0.0, "median": 0.0, "q3": 0.0, "max": 0.0, "mean": 0.0}
            arr = np.asarray(values, dtype=float)
            return {
                "min": round(float(np.min(arr)), 2),
                "q1": round(float(np.percentile(arr, 25)), 2),
                "median": round(float(np.median(arr)), 2),
                "q3": round(float(np.percentile(arr, 75)), 2),
                "max": round(float(np.max(arr)), 2),
                "mean": round(float(np.mean(arr)), 2),
            }

        technique_cards = [
            self._technique_card(
                "Front Knee at Release",
                front_knee_br_score,
                f"{front_knee_at_release:.1f}° at ball release — locked brace supports energy transfer.",
            ),
            self._technique_card(
                "Pelvis-Shoulder Separation",
                ps_sep_score,
                f"{ps_sep_at_release:.1f}° of torso wind-up at release (ideal 35-45°).",
            ),
            self._technique_card(
                "Trunk Lateral Flexion",
                trunk_score,
                f"{trunk_flex_at_release:.1f}° sideways tilt at release. Excess increases lumbar load.",
            ),
            self._technique_card(
                "Release Angle",
                release_angle_score,
                f"{release_angle:.1f}° from vertical — smaller means more overhead release.",
            ),
            self._technique_card(
                "Shoulder Alignment",
                shoulder_score,
                f"Average {shoulder_align_arr.mean():.1f}° deviation from horizontal.",
            ),
            self._technique_card(
                "Run-up Speed",
                runup_speed_score,
                f"Approach tempo {runup_speed_kph:.1f} kph into the crease.",
            ),
        ]

        good_points: list[str] = []
        errors_detected: list[str] = []
        if front_knee_br_score >= 70:
            good_points.append("Front leg braces strongly at release, a key marker of elite fast bowlers.")
        else:
            errors_detected.append("Front knee collapses through release — brace earlier to retain energy.")
        if 32 <= ps_sep_at_release <= 55:
            good_points.append("Pelvis-shoulder separation is within the elite 35-45° window.")
        else:
            errors_detected.append("Pelvis-shoulder separation is outside the 35-45° elite band.")
        if trunk_flex_at_release > 28:
            errors_detected.append("High trunk lateral flexion at release raises lumbar stress risk.")
        elif trunk_flex_at_release < 18:
            errors_detected.append("Limited lateral flexion limits release point and delivery stride.")
        else:
            good_points.append("Trunk lateral flexion at release sits in the recommended 18-28° band.")

        injury_risk = [
            {
                "label": "Lumbar Stress",
                "level": "High" if trunk_flex_at_release > 30 else "Moderate" if trunk_flex_at_release > 22 else "Low",
                "detail": "Based on trunk lateral flexion at ball release (Portus et al. threshold ~30°).",
            },
            {
                "label": "Front Knee Load",
                "level": "High" if vGRF_bw > 7 else "Moderate" if vGRF_bw > 5 else "Low",
                "detail": f"Estimated peak vGRF of {vGRF_bw:.1f} body-weights at FFC.",
            },
            {
                "label": "Shoulder Alignment Drift",
                "level": "Moderate" if shoulder_align_arr.mean() > 14 else "Low",
                "detail": "Average shoulder line deviation from horizontal across the run-up.",
            },
            {
                "label": "Mixed-action Flag",
                "level": "High" if action_type == "mixed" else "Low",
                "detail": "Shoulder-hip counter-rotation >20° between BFC and FFC is the strongest published lumbar-stress risk marker.",
            },
            {
                "label": "Front Knee Hyperextension",
                "level": "High" if front_knee_hyperextend else "Moderate" if front_knee_at_release > 178 else "Low",
                "detail": f"Front knee extension {front_knee_at_release:.1f}° at release (hyperextension risk >182°).",
            },
            {
                "label": "Landing Mechanics",
                "level": "High" if landing_balance_score < 50 else "Moderate" if landing_balance_score < 65 else "Low",
                "detail": "Based on COM horizontal stability in the 0.15s window after front-foot plant.",
            },
            {
                "label": "Kinematic Asymmetry",
                "level": "Moderate" if symmetry_score < 65 else "Low",
                "detail": "Compares mean knee extension between left and right leg across the delivery.",
            },
        ]

        coaching_tips = [
            {
                "title": "Lock the Front Leg Early",
                "detail": "Aim to reach >165° of front-knee extension at release to improve energy transfer into the ball.",
                "severity": "medium" if front_knee_at_release < 165 else "low",
            },
            {
                "title": "Deepen Pelvis-Shoulder Separation",
                "detail": "Target 35-45° of separation at release by delaying shoulder rotation after front-foot plant.",
                "severity": "medium" if not 32 <= ps_sep_at_release <= 55 else "low",
            },
            {
                "title": "Control Lateral Flexion",
                "detail": "Keep lateral trunk tilt under 28° at release to protect the lumbar spine.",
                "severity": "high" if trunk_flex_at_release > 30 else "low",
            },
            {
                "title": "Avoid Mixed-Action Counter-Rotation",
                "detail": "Match shoulder alignment with hip rotation between back-foot and front-foot contact — mixed actions have the strongest published injury link.",
                "severity": "high" if action_type == "mixed" else "low",
            },
        ]

        comparison_inputs = {
            "release_angle": round(release_angle, 1),
            "front_knee_brace": round(front_knee_at_release, 1),
            "back_leg_drive": round(normalize_score(float(knee_back_arr.mean()), 160.0, 20.0), 1),
            "shoulder_alignment": round(shoulder_score, 1),
            "hip_rotation": round(ps_sep_at_release, 1),
            "bowling_arm_speed": round(release_speed_score, 1),
            "elbow_extension": round(
                angle_between_points(
                    samples[release].landmarks[f"{bowling_side}_shoulder"],
                    samples[release].landmarks[f"{bowling_side}_elbow"],
                    samples[release].landmarks[f"{bowling_side}_wrist"],
                ),
                1,
            ),
            "head_stability": round(clamp(100 - float(np.std([f.landmarks["nose"][0] for f in samples])) * 400, 0, 100), 1),
            "follow_through_balance": round(follow_through_balance, 1),
            "stride_length": round(stride_length_m, 2),
            "runup_consistency": round(runup_consistency_score, 1),
            "overall_efficiency": round(efficiency_score, 1),
        }

        return {
            "video_meta": {
                "fps": round(fps, 2),
                "total_frames": total_frames,
                "analyzed_frames": len(samples),
                "width": width,
                "height": height,
                "bowling_arm": bowling_side,
            },
            "assets": {
                "thumbnail_path": None,
                "processed_video_path": None,
                "original_video_path": None,
            },
            "joint_metrics": {
                "release_angle_deg": round(release_angle, 1),
                "release_height_m": round(release_height_m, 2),
                "wrist_velocity_mps": round(wrist_velocity_mps, 2),
                "hip_rotation_speed_dps": round(hip_rotation_speed_dps, 1),
                "landing_balance_score": round(landing_balance_score, 1),
                "symmetry_score": round(symmetry_score, 1),
                "shoulder_alignment_deg": round(float(shoulder_align_arr.mean()), 1),
                "pelvis_shoulder_separation_deg": round(ps_sep_at_release, 1),
                "trunk_lateral_flexion_deg": round(trunk_flex_at_release, 1),
                "front_knee_flexion_ffc_deg": round(front_knee_at_ffc, 1),
                "front_knee_flexion_br_deg": round(front_knee_at_release, 1),
                "knee_flexion_change_deg": round(knee_flexion_change, 1),
                "stride_length_m": round(stride_length_m, 2),
                "runup_speed_kph": round(runup_speed_kph, 1),
                "release_speed_kph": round(release_speed_kph, 1),
                "vGRF_body_weights": round(vGRF_bw, 2),
                "vGRF_newtons": round(vGRF_N, 1),
            },
            "classification": {
                "action_type": action_type,
                "action_label": action_label_map[action_type],
                "confidence": round(action_confidence, 1),
                "shoulder_at_bfc_deg": round(shoulder_bfc, 1),
                "shoulder_at_ffc_deg": round(shoulder_ffc, 1),
                "shoulder_delta_deg": round(shoulder_delta, 1),
                "description": action_description_map[action_type],
            },
            "injury_analysis": {
                "probability": round(injury_probability, 1),
                "band": injury_band,
                "contributors": contributors,
            },
            "timing_metrics": {
                "delivery_duration_s": round(samples[-1].timestamp - samples[0].timestamp, 2),
                "ffc_to_release_ms": round((samples[release].timestamp - samples[ffc].timestamp) * 1000.0, 1),
                "release_frame": samples[release].frame_index,
                "release_time_s": round(samples[release].timestamp, 3),
                "front_foot_landing_frame": samples[ffc].frame_index,
                "front_foot_landing_time_s": round(samples[ffc].timestamp, 3),
            },
            "scores": {
                "shoulder_alignment": round(shoulder_score, 1),
                "pelvis_shoulder_separation": round(ps_sep_score, 1),
                "trunk_lateral_flexion": round(trunk_score, 1),
                "front_knee_at_ffc": round(front_knee_ffc_score, 1),
                "front_knee_at_release": round(front_knee_br_score, 1),
                "release_angle": round(release_angle_score, 1),
                "release_speed": round(release_speed_score, 1),
                "runup_speed": round(runup_speed_score, 1),
                "stride_length": round(stride_length_score, 1),
                "follow_through_balance": round(follow_balance_score, 1),
                "runup_consistency": round(runup_consistency_score, 1),
                "vGRF": round(vGRF_score, 1),
            },
            "comparison_inputs": comparison_inputs,
            "comparison_metrics": [
                {"metric": "Release Angle", "athlete": round(release_angle, 1), "benchmark": 12.0, "delta": round(release_angle - 12.0, 1), "unit": "deg"},
                {"metric": "Front Leg Brace", "athlete": round(front_knee_at_release, 1), "benchmark": 170.0, "delta": round(front_knee_at_release - 170.0, 1), "unit": "deg"},
                {"metric": "Pelvis-Shoulder Separation", "athlete": round(ps_sep_at_release, 1), "benchmark": 42.0, "delta": round(ps_sep_at_release - 42.0, 1), "unit": "deg"},
                {"metric": "Stride Length", "athlete": round(stride_length_m, 2), "benchmark": 1.85, "delta": round(stride_length_m - 1.85, 2), "unit": "m"},
            ],
            "technique_cards": technique_cards,
            "frame_events": frame_events,
            "motion_series": {
                "bowling_arm_angle": _series(arm_arr, "bowling_arm_angle"),
                "shoulder_alignment": _series(shoulder_align_arr, "shoulder_alignment"),
                "front_knee_bend": _series(knee_front_arr, "front_knee_bend"),
                "trunk_lateral_flexion": _series(trunk_flex_arr, "trunk_lateral_flexion"),
                "pelvis_shoulder_separation": _series(ps_sep_arr, "pelvis_shoulder_separation"),
                "back_knee_bend": _series(knee_back_arr, "back_knee_bend"),
                "wrist_trajectory": [
                    {
                        "frame": samples[i].frame_index,
                        "timestamp": round(samples[i].timestamp, 3),
                        "x": round(float(samples[i].landmarks[f"{bowling_side}_wrist"][0]) * 100, 2),
                        "y": round(
                            100 - float(samples[i].landmarks[f"{bowling_side}_wrist"][1]) * 100,
                            2,
                        ),
                    }
                    for i in range(len(samples))
                ],
                "symmetry": [
                    {
                        "frame": samples[i].frame_index,
                        "timestamp": round(samples[i].timestamp, 3),
                        "left": round(float(knee_front_arr[i]) if front_key == "left" else float(knee_back_arr[i]), 2),
                        "right": round(float(knee_front_arr[i]) if front_key == "right" else float(knee_back_arr[i]), 2),
                    }
                    for i in range(len(samples))
                ],
                "risk_heatmap": [
                    {
                        "frame": samples[i].frame_index,
                        "timestamp": round(samples[i].timestamp, 3),
                        "trunk_flex": round(float(trunk_flex_arr[i]), 2),
                        "band": (
                            "high"
                            if float(trunk_flex_arr[i]) >= 30
                            else "moderate"
                            if float(trunk_flex_arr[i]) >= 22
                            else "low"
                        ),
                    }
                    for i in range(len(samples))
                ],
            },
            "distribution_stats": {
                "shoulder_alignment": _boxplot(shoulder_align_arr),
                "pelvis_shoulder_separation": _boxplot(ps_sep_arr),
                "trunk_lateral_flexion": _boxplot(trunk_flex_arr),
                "front_knee_bend": _boxplot(knee_front_arr),
            },
            "good_points": good_points,
            "errors_detected": errors_detected,
            "injury_risk": injury_risk,
            "coaching_tips": coaching_tips,
            "estimation_notes": [
                "Speeds, stride length, and vGRF are single-camera estimates derived from a 1.82m body-height scale.",
                "Bowling arm is auto-detected from peak wrist height across the delivery.",
                "Architecture is ready for multi-camera calibrated capture and radar ground-truth in future upgrades.",
            ],
            "summary": {
                "overall_score": overall_score,
                "efficiency_score": round(efficiency_score, 1),
                "balance_score": round(balance_score, 1),
                "consistency_score": round(consistency_score, 1),
                "motion_smoothness_score": round(smoothness, 1),
                "approx_speed_kph": round(release_speed_kph, 1),
            },
        }

    def _technique_card(self, label: str, score: float, insight: str) -> dict:
        if score >= 80:
            status = "Elite"
        elif score >= 65:
            status = "Strong"
        elif score >= 50:
            status = "Developing"
        else:
            status = "Needs Work"
        return {"label": label, "score": round(score, 1), "status": status, "insight": insight}
