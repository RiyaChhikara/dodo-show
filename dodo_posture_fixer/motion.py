"""Sit-up nag vs rest. goto_target for the pose change; no recorded audio."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any

MIN_STEP_DURATION_S = 0.5
MAX_HEAD_DEG = 16.0
MAX_ANTENNA_RAD = 0.32


@dataclass(frozen=True)
class HeadStep:
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    left_antenna: float = 0.0
    right_antenna: float = 0.0
    duration_s: float = MIN_STEP_DURATION_S


NAG = HeadStep(pitch=-12.0, yaw=6.0, left_antenna=0.28, right_antenna=-0.28, duration_s=0.55)
REST = HeadStep(duration_s=0.55)


def clamp_step(step: HeadStep) -> HeadStep:
    return HeadStep(
        yaw=_clamp(step.yaw, MAX_HEAD_DEG),
        pitch=_clamp(step.pitch, MAX_HEAD_DEG),
        roll=_clamp(step.roll, MAX_HEAD_DEG),
        left_antenna=_clamp(step.left_antenna, MAX_ANTENNA_RAD),
        right_antenna=_clamp(step.right_antenna, MAX_ANTENNA_RAD),
        duration_s=max(step.duration_s, MIN_STEP_DURATION_S),
    )


def go_pose(reachy: Any | None, slouch: bool, stop_event: Event | None = None, *, dry_run: bool = False) -> str:
    name = "nag" if slouch else "rest"
    step = clamp_step(NAG if slouch else REST)
    if dry_run or reachy is None:
        return f"[dry-run] {name} pitch={step.pitch:.1f}"
    if stop_event is not None and stop_event.is_set():
        return f"skipped:{name}"
    _goto_step(reachy, step)
    return f"move:{name}"


def _goto_step(reachy: Any, step: HeadStep) -> None:
    try:
        from reachy_mini.utils import create_head_pose

        head = create_head_pose(roll=step.roll, pitch=step.pitch, yaw=step.yaw, degrees=True)
    except ImportError:
        head = (step.roll, step.pitch, step.yaw)
    reachy.goto_target(
        head=head,
        antennas=[step.left_antenna, step.right_antenna],
        duration=step.duration_s,
    )


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))
