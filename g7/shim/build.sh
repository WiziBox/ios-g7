#!/usr/bin/env bash
set -euo pipefail
# G7 currently supports only the verified display diagnostic.
exec bash "$(dirname -- "$0")/../build-diag.sh" "$@"
