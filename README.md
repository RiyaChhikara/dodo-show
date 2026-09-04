---
title: Dodo Posture Fixer
emoji: 🪑
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
short_description: Dodo nags when you slouch at the desk.
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# Dodo Posture Fixer

Sit in Dodo’s camera. If your shoulders drop or tilt, she does a small sit-up of her own and looks at you until you copy her. Sit straight, she settles.

Local **MediaPipe Pose**. No cloud. No gym science. A desk companion with opinions.

## What you should see

1. Open shows the whole camera frame (16:9 contain, not a cropped chin).
2. Slouch / uneven shoulders → pill says **Sit up**, she `goto_target()` nags.
3. Sit up for a few frames → **Looking good**, rest pose.
4. Pause if you need her to stop watching.

Stop other vision apps first. Only one app can own the camera.

**TODO: confirm slouch + nag on Dodo hardware.** Dry-run only proves the landmark math.

## Run (no motors)

```bash
PYTHONPATH=apps/dodo_posture_fixer python -m dodo_posture_fixer.main --dry-run
pytest tests/test_posture_fixer.py
```

## Install on Dodo

Stop whatever is running. Slot must be Ready.

```bash
bash apps/dodo_posture_fixer/install-on-dodo.sh
```

Confirm `INSTALLED 0.1.0` and `OPEN_URL http://0.0.0.0:8064`. Then Start → Open.

## How slouch is decided

- MediaPipe Pose landmarks: nose + both shoulders.
- Uneven shoulders (`|left.y − right.y|` big) **or** head dropped toward the shoulders.
- A few frames on, a few frames off, so a blur does not count.
