#!/usr/bin/env bash
# Compile with interpreter symbols needed to import Lean environment extensions.
set -euo pipefail
MAAM_EXPORT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$MAAM_EXPORT_ROOT/build/native"
cp "$MAAM_EXPORT_ROOT/maam/PaperExport.lean" "$MAAM_EXPORT_ROOT/build/native/PaperExport.lean"
cp "$MAAM_EXPORT_ROOT/lean/native/lakefile.lean" "$MAAM_EXPORT_ROOT/build/native/lakefile.lean"
cp "$MAAM_EXPORT_ROOT/lean/lean-toolchain" "$MAAM_EXPORT_ROOT/build/native/lean-toolchain"
(cd "$MAAM_EXPORT_ROOT/build/native" && lake build maam-paper-export)
cp "$MAAM_EXPORT_ROOT/build/native/.lake/build/bin/maam-paper-export" \
  "$MAAM_EXPORT_ROOT/build/maam-paper-export"
