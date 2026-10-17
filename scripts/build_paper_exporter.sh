#!/usr/bin/env bash
# Compile the unchanged Lean exporter through Lean's official C backend.
set -euo pipefail
MAAM_EXPORT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$MAAM_EXPORT_ROOT/build"
lean -o "$MAAM_EXPORT_ROOT/build/PaperExport.olean" \
  -c "$MAAM_EXPORT_ROOT/build/PaperExport.c" "$MAAM_EXPORT_ROOT/maam/PaperExport.lean"
leanc -O3 -o "$MAAM_EXPORT_ROOT/build/maam-paper-export" \
  "$MAAM_EXPORT_ROOT/build/PaperExport.c"
