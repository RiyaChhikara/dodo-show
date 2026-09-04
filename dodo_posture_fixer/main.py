"""Dodo Posture Fixer: slouch in the camera, she nags until you sit up."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from threading import Event, Lock
from typing import Any

APP_DIR = Path(__file__).resolve().parent
if __package__ in {None, ""}:
    sys.path.insert(0, str(APP_DIR.parent))
    from dodo_posture_fixer.camera import try_reachy_frame
    from dodo_posture_fixer.motion import go_pose
    from dodo_posture_fixer.pose import SlouchTracker, annotate, is_slouch, make_landmarks, make_pose, observe_frame
else:
    from .camera import try_reachy_frame
    from .motion import go_pose
    from .pose import SlouchTracker, annotate, is_slouch, make_landmarks, make_pose, observe_frame

try:
    from reachy_mini import ReachyMini, ReachyMiniApp
except ImportError:
    ReachyMini = None  # type: ignore[misc, assignment]
    ReachyMiniApp = object  # type: ignore[misc, assignment]

LOGGER = logging.getLogger("reachy_mini.app")
LOOP_PAUSE_S = 0.08
NAG_EVERY_S = 2.4


def say(message: str) -> None:
    print(message, flush=True)
    LOGGER.info(message)


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    slouch = bool(state.get("slouch"))
    if slouch:
        pill = "Sit up"
        headline = "I see you folding"
    elif state.get("listening") == "paused":
        pill = "Paused"
        headline = "Not watching"
    else:
        pill = "Looking good"
        headline = "Shoulders look level"
    return {
        "listening": state.get("listening") or "",
        "pill": pill,
        "headline": headline,
        "detail": state.get("detail") or "",
        "slouch": slouch,
        "hold": bool(state.get("hold")),
        "camera": state.get("camera") or "",
        "cue": state.get("cue") or "",
        "last_error": state.get("last_error") or "",
    }


def run_dry_run() -> None:
    print("Dodo Posture Fixer dry-run (no robot, no MediaPipe).")
    tracker = SlouchTracker(on_frames=2, off_frames=2)
    scenes = (
        ("upright", "upright"),
        ("upright", "upright"),
        ("slouch", "slouch"),
        ("slouch", "slouch"),
        ("slouch", "slouch"),
        ("upright", "upright"),
        ("upright", "upright"),
        ("tilted", "tilted"),
        ("tilted", "tilted"),
    )
    last = False
    for label, kind in scenes:
        raw = is_slouch(make_landmarks(kind))
        present = tracker.update(raw)
        if present != last:
            print(go_pose(None, present, dry_run=True), f"after {label}")
            last = present
        else:
            print(f"{label}: slouch={raw} tracking={present}")


def watch_loop(reachy: Any, stop_event: Event, state: dict[str, Any]) -> None:
    say("Press Open. Sit in frame. Slouch and Dodo nags. Sit up and she settles.")
    media = getattr(reachy, "media", None)
    pose = make_pose()
    tracker = SlouchTracker()
    state["camera"] = "mediapipe" if pose is not None else "no detector"
    if pose is None:
        state["last_error"] = "MediaPipe Pose missing. Next still works as a fake slouch."
        say(state["last_error"])
    last_slouch = False
    last_nag = 0.0
    try:
        while not stop_event.is_set():
            if state.get("hold"):
                state["listening"] = "paused"
                time.sleep(LOOP_PAUSE_S)
                continue
            frame = try_reachy_frame(media)
            if frame is None:
                state["camera"] = "no-frames"
                state["cue"] = "no camera frame"
                time.sleep(0.1)
                continue
            state["camera"] = "dodo"
            if pose is None:
                hit_slouch = bool(state.pop("pending_slouch", False))
                reason = "tap Sit up on Open (no Pose)"
                preview = frame
            else:
                hit = observe_frame(frame, pose)
                hit_slouch = hit.slouch
                reason = hit.reason
                preview = annotate(frame, hit)
            present = tracker.update(hit_slouch)
            state["preview"] = preview
            state["cue"] = reason
            state["slouch"] = present
            state["detail"] = reason
            state["listening"] = "nagging" if present else "watching"
            now = time.monotonic()
            if present != last_slouch:
                say(go_pose(reachy, present, stop_event))
                last_slouch = present
                last_nag = now
            elif present and now - last_nag >= NAG_EVERY_S:
                say(go_pose(reachy, True, stop_event))
                last_nag = now
            time.sleep(LOOP_PAUSE_S)
    finally:
        closer = getattr(pose, "close", None)
        if callable(closer):
            closer()


class DodoPostureFixer(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8064"
    request_media_backend: str | None = "default"

    def __init__(self) -> None:
        super().__init__()
        self.state: dict[str, Any] = {
            "lock": Lock(),
            "listening": "starting",
            "slouch": False,
            "detail": "Sit where Dodo can see your shoulders.",
            "hold": False,
            "camera": "starting",
            "cue": "",
            "last_error": "",
            "preview": None,
        }
        if self.settings_app is None:
            return
        from fastapi.responses import StreamingResponse
        from starlette.responses import JSONResponse

        @self.settings_app.get("/video_feed")
        def video_feed() -> Any:
            return StreamingResponse(
                self._frame_generator(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

        @self.settings_app.get("/status")
        def live_status() -> dict[str, Any]:
            return public_state(self.state)

        async def talk(request: Any) -> Any:
            try:
                body = await request.json()
                action = str(body.get("action") or "").strip().lower()
                if action == "pause":
                    self.state["hold"] = True
                    return JSONResponse({"ok": True, "action": "pause"})
                if action == "resume":
                    self.state["hold"] = False
                    return JSONResponse({"ok": True, "action": "resume"})
                if action == "slouch":
                    self.state["pending_slouch"] = True
                    return JSONResponse({"ok": True, "action": "slouch"})
                return JSONResponse({"ok": False, "error": "Use pause, resume, or slouch."})
            except Exception as exc:
                self.state["last_error"] = str(exc)
                return JSONResponse({"ok": False, "error": str(exc)})

        self.settings_app.add_route("/talk", talk, methods=["POST"])

    def _frame_generator(self) -> Any:
        import cv2

        while True:
            frame = self.state.get("preview")
            if frame is None:
                time.sleep(0.05)
                continue
            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                time.sleep(0.05)
                continue
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            )
            time.sleep(0.06)

    def run(self, reachy_mini: Any, stop_event: Event) -> None:
        say("Open http://0.0.0.0:8064")
        watch_loop(reachy_mini, stop_event, self.state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dodo nags when you slouch.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        run_dry_run()
        return
    if ReachyMiniApp is object or ReachyMini is None:
        raise SystemExit("Install the Reachy Mini SDK first, or use --dry-run.")
    app = DodoPostureFixer()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        app = DodoPostureFixer()
        try:
            app.wrapped_run()
        except KeyboardInterrupt:
            app.stop()
