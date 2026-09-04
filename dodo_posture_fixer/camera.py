"""Read frames the official Wireless way: reachy.media.get_frame()."""

from __future__ import annotations

from typing import Any


def is_usable_frame(frame: Any) -> bool:
    if frame is None:
        return False
    try:
        return int(getattr(frame, "size", 0)) > 0 and getattr(frame, "ndim", 0) == 3
    except (TypeError, ValueError):
        return False


def try_reachy_frame(media: Any) -> Any | None:
    if media is None:
        return None
    getter = getattr(media, "get_frame", None)
    if not callable(getter):
        return None
    try:
        frame = getter()
    except Exception:
        return None
    return frame if is_usable_frame(frame) else None
