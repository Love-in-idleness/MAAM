#!/usr/bin/env bash
# Compile the auditor with shared-expression traversal for dependency sets.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: $0 MATHLIB_CHECKOUT NEW_OUTPUT_DIRECTORY" >&2
  exit 2
fi
root="$(cd "$(dirname "$0")/.." && pwd)"
mathlib="$(cd "$1" && pwd)"
mkdir -- "$2"
output="$(cd "$2" && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf -- "$scratch"' EXIT

cp "$root/maam/PackageCheck.lean" "$root/lean/lean-toolchain" "$scratch/"
python - "$scratch/PackageCheck.lean" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
original = """    let (_, signatureNames) ← IO.ofExcept (exprStats info.type)
    queue := queue ++ signatureNames.toArray
    if let some value := info.value? (allowOpaque := true) then
      let (_, valueNames) ← IO.ofExcept (exprStats value)
      queue := queue ++ valueNames.toArray"""
replacement = """    queue := queue ++ info.type.getUsedConstants
    if let some value := info.value? (allowOpaque := true) then
      queue := queue ++ value.getUsedConstants"""
if source.count(original) != 1:
    raise SystemExit("cannot locate pinned dependency traversal")
path.write_text(source.replace(original, replacement), encoding="utf-8")
PY
sha256sum "$scratch/PackageCheck.lean" | cut -d ' ' -f1 > "$output/native-auditor-source.sha256"
sed -e 's/maam_paper_export/maam_package_check/' \
    -e 's/maam-paper-export/maam-package-check/' \
    -e 's/PaperExport/PackageCheck/' "$root/lean/native/lakefile.lean" > "$scratch/lakefile.lean"
(cd "$scratch" && lake build maam-package-check)

MAAM_PANEL_LEAN="$(command -v lean)"
MAAM_PANEL_LEAN="$(cd "$(dirname "$MAAM_PANEL_LEAN")" && pwd)/$(basename "$MAAM_PANEL_LEAN")"
MAAM_PANEL_SYSROOT="$(lean --print-prefix)"
export MAAM_PANEL_LEAN MAAM_PANEL_SYSROOT
export MAAM_PANEL_CHECKER="$scratch/.lake/build/bin/maam-package-check"
cat > "$scratch/lean-with-native-audit" <<'RUNNER'
#!/usr/bin/env bash
set -eu
if [[ "${1:-}" == --run && "${2##*/}" == PackageCheck.lean ]]; then
  shift 2
  export LEAN_SYSROOT="$MAAM_PANEL_SYSROOT"
  exec "$MAAM_PANEL_CHECKER" "$@"
fi
exec "$MAAM_PANEL_LEAN" "$@"
RUNNER
chmod +x "$scratch/lean-with-native-audit"

panel="$root/experiments/conjecture_compression_v2"
cp "$panel"/*.lean "$panel"/*-suite.json "$panel/panel.json" "$output/"
cd "$root"
for target in euclid bertrand; do
  python scripts/measure_conjecture_panel_suite.py --lean "$scratch/lean-with-native-audit" \
    --auditor-source "$scratch/PackageCheck.lean" --mathlib "$mathlib" \
    --suite "$output/$target-suite.json" --output "$output/$target-report.json"
done
python scripts/rank_conjecture_compression_panel.py --panel "$output/panel.json" > "$output/ranking.json"
python scripts/rank_conjecture_compression_panel.py --panel "$output/panel.json" --format markdown > "$output/ranking.md"
