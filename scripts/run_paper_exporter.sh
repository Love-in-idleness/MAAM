#!/usr/bin/env bash
# Export with a small local progress file and ordinary process logs.
set -euo pipefail
MAAM_EXPORT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$MAAM_EXPORT_ROOT/data"
export MAAM_PROGRESS_FILE="$MAAM_EXPORT_ROOT/data/mathlib-progress.txt"
printf 'starting' > "$MAAM_PROGRESS_FILE"
MAAM_EXPORT_START=$SECONDS
/usr/bin/time -v "$MAAM_EXPORT_ROOT/build/maam-paper-export" "$@" &
MAAM_EXPORT_PID=$!

while kill -0 "$MAAM_EXPORT_PID" 2>/dev/null; do
  MAAM_EXPORT_MESSAGE="$(cat "$MAAM_PROGRESS_FILE")"
  MAAM_EXPORT_RSS="$( { ps --ppid "$MAAM_EXPORT_PID" -o rss= || true; } | awk '{sum+=$1} END {print int(sum/1024)}')"
  printf '%s\n' "$MAAM_EXPORT_MESSAGE; rss=${MAAM_EXPORT_RSS}MB; elapsed=$((SECONDS-MAAM_EXPORT_START))s"
  sleep "${MAAM_PROGRESS_INTERVAL:-30}"
done
set +e
wait "$MAAM_EXPORT_PID"
MAAM_EXPORT_RESULT=$?
set -e
if [ "$MAAM_EXPORT_RESULT" -eq 0 ]; then
  cat "$MAAM_PROGRESS_FILE"
else
  printf '%s\n' "export failed; exit=$MAAM_EXPORT_RESULT; $(cat "$MAAM_PROGRESS_FILE")"
fi
exit "$MAAM_EXPORT_RESULT"
