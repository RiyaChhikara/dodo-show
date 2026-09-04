"""Shoulder / slouch cue from MediaPipe Pose landmarks. No cloud."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NOSE, LEFT_SHOULDER, RIGHT_SHOULDER = 0, 11, 12
TILT_SLOUCH = 0.045
DROP_SLOUCH = 0.32
MIN_SHOULDER_WIDTH = 0.08
NEED_FRAMES = 3
LOST_FRAMES = 4


@dataclass(frozen=True)
class PoseHit:
    slouch: bool
    reason: str
    tilt: float = 0.0
    drop: float = 0.0
    box: tuple[int, int, int, int] | None = None


class _Point:
    def __init__(self, px: float, py: float, visibility: float = 1.0) -> None:
        self.x = px
        self.y = py
        self.visibility = visibility


def _xy(landmark: Any) -> tuple[float, float]:
    if hasattr(landmark, "y"):
        return (float(landmark.x), float(landmark.y))
    return (float(landmark[0]), float(landmark[1]))


def _visible(landmark: Any) -> bool:
    vis = float(getattr(landmark, "visibility", 1.0) or 0.0)
    return vis >= 0.45


def shoulder_metrics(landmarks: Any) -> tuple[float, float] | None:
    """Return (tilt, head_drop_ratio) or None if the torso is missing."""

    if landmarks is None or len(landmarks) <= RIGHT_SHOULDER:
        return None
    nose, left, right = landmarks[NOSE], landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER]
    if not (_visible(left) and _visible(right) and _visible(nose)):
        return None
    lx, ly = _xy(left)
    rx, ry = _xy(right)
    nx, ny = _xy(nose)
    width = abs(rx - lx)
    if width < MIN_SHOULDER_WIDTH:
        return None
    tilt = abs(ly - ry)
    mid_y = (ly + ry) / 2.0
    drop = (mid_y - ny) / width
    return (tilt, drop)


def is_slouch(landmarks: Any) -> bool:
    metrics = shoulder_metrics(landmarks)
    if metrics is None:
        return False
    tilt, drop = metrics
    return tilt >= TILT_SLOUCH or drop <= DROP_SLOUCH


def landmark_box(landmarks: Any, width: int, height: int) -> tuple[int, int, int, int]:
    xs = [_xy(item)[0] for item in (landmarks[NOSE], landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER])]
    ys = [_xy(item)[1] for item in (landmarks[NOSE], landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER])]
    x0 = int(max(0, min(xs) * width) - 16)
    y0 = int(max(0, min(ys) * height) - 16)
    x1 = int(min(width, max(xs) * width) + 16)
    y1 = int(min(height, max(ys) * height) + 16)
    return (x0, y0, max(8, x1 - x0), max(8, y1 - y0))


class SlouchTracker:
    """Need a few slouch frames on, a few clean frames off."""

    def __init__(self, on_frames: int = NEED_FRAMES, off_frames: int = LOST_FRAMES) -> None:
        self.on_frames = max(1, int(on_frames))
        self.off_frames = max(1, int(off_frames))
        self.present = False
        self._hit = 0
        self._miss = 0

    def update(self, slouch: bool) -> bool:
        if slouch:
            self._miss = 0
            self._hit += 1
            if self._hit >= self.on_frames:
                self.present = True
        else:
            self._hit = 0
            self._miss += 1
            if self._miss >= self.off_frames:
                self.present = False
        return self.present


def observe_frame(frame: Any, pose: Any | None) -> PoseHit:
    if frame is None or pose is None:
        return PoseHit(False, "no camera or detector")
    import cv2

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose.process(rgb)
    if not result.pose_landmarks:
        return PoseHit(False, "no person")
    landmarks = result.pose_landmarks.landmark
    metrics = shoulder_metrics(landmarks)
    height, width = frame.shape[:2]
    box = landmark_box(landmarks, width, height)
    if metrics is None:
        return PoseHit(False, "need shoulders in view", box=box)
    tilt, drop = metrics
    if tilt >= TILT_SLOUCH:
        return PoseHit(True, "shoulders uneven", tilt=tilt, drop=drop, box=box)
    if drop <= DROP_SLOUCH:
        return PoseHit(True, "head dropped", tilt=tilt, drop=drop, box=box)
    return PoseHit(False, "sitting up", tilt=tilt, drop=drop, box=box)


def make_pose() -> Any | None:
    try:
        import mediapipe as mp

        return mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    except Exception:
        return None


def annotate(frame: Any, hit: PoseHit) -> Any:
    import cv2

    preview = frame.copy()
    if hit.box:
        x, y, w, h = hit.box
        color = (70, 90, 230) if hit.slouch else (80, 220, 160)
        cv2.rectangle(preview, (x, y), (x + w, y + h), color, 2)
    label = "sit up" if hit.slouch else hit.reason
    cv2.putText(preview, label, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (232, 160, 74), 2, cv2.LINE_AA)
    return preview


def make_landmarks(kind: str) -> list[_Point]:
    """Synthetic Pose points for tests and dry-run. kind: upright, slouch, tilted."""

    points = [_Point(0.5, 0.5, 0.1) for _ in range(33)]
    if kind == "upright":
        points[NOSE] = _Point(0.50, 0.22)
        points[LEFT_SHOULDER] = _Point(0.38, 0.48)
        points[RIGHT_SHOULDER] = _Point(0.62, 0.48)
        return points
    if kind == "slouch":
        points[NOSE] = _Point(0.50, 0.40)
        points[LEFT_SHOULDER] = _Point(0.38, 0.46)
        points[RIGHT_SHOULDER] = _Point(0.62, 0.46)
        return points
    if kind == "tilted":
        points[NOSE] = _Point(0.50, 0.22)
        points[LEFT_SHOULDER] = _Point(0.38, 0.40)
        points[RIGHT_SHOULDER] = _Point(0.62, 0.52)
        return points
    return points
