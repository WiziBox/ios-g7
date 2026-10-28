#!/usr/bin/env bash
set -euo pipefail
# The old path ran SWEET framebuffer/UFS code with an empty payload.
# Until a G7 XNU port exists, the supported target is a display-only diagnostic.
exec bash "$(dirname -- "$0")/build-diag.sh" "$@"
