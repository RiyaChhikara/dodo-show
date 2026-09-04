#!/bin/bash
# Thin wrapper. The real path is scripts/install-on-dodo.sh (Dodo only).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$REPO/scripts/install-on-dodo.sh" dodo_posture_fixer DodoPostureFixer
