# Dodo Posture Fixer plan

## User experience

Riya slumps at the desk. Dodo notices shoulders drop or tilt, sits up a little herself, and looks until Riya copies her. Sit straight, Dodo rests.

## Technical approach

- Same Python app: `ReachyMiniApp`, Open `http://0.0.0.0:8064`.
- Camera: `get_frame()` + MediaPipe Pose.
- Slouch = uneven shoulders **or** head dropped toward the shoulder line. Debounced.
- `goto_target()` nag pose on the rising edge, again every ~2.4s while still slouching. Rest on the falling edge.
- `--dry-run` uses synthetic landmarks. No network.
- Fake slouch button on Open if Pose is missing.

## Open questions

- [ ] Does a desk-distance torso read clearly in Dodo’s wide camera?
- [ ] Does the nag pose read as “sit up” and not as a random twitch?
- [ ] Side-on sitting (one shoulder hidden) — skip or still fire?
