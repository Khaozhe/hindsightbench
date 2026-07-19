#!/bin/bash
# HindsightBench top-level driver: one command from model key to leaderboard.
#
#   ./run_bench.sh <model-key> smoke     # 2 dates x 4 arms, then STOP for manual inspection
#   ./run_bench.sh <model-key> arms      # full arm matrix (idempotent resume)
#   ./run_bench.sh <model-key> probes    # date-recovery + LAP probes
#   ./run_bench.sh <model-key> row       # analyze -> <key>_row.json + regenerate tables
#   ./run_bench.sh <model-key> all       # arms -> probes -> row (smoke must have been inspected)
#   DRY_RUN=1 ./run_bench.sh <key> all   # print the commands without calling any API
#
# The model must exist in models.yaml. The preregistration (BM1_prereg.md)
# requires a smoke run with MANUAL inspection before full volume — `all`
# refuses to start if no smoke cells exist for the model.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${HINDSIGHT_PY:-python3}"
KEY="${1:?usage: run_bench.sh <model-key> smoke|arms|probes|row|all}"
PHASE="${2:?usage: run_bench.sh <model-key> smoke|arms|probes|row|all}"

PROVIDER="$($PY -c "import yaml; print(yaml.safe_load(open('$HERE/models.yaml'))['$KEY']['provider'])")"
TIER="$($PY -c "import yaml; print(yaml.safe_load(open('$HERE/models.yaml'))['$KEY']['tier'])")"

if [ "$PROVIDER" = "gemini-legacy" ]; then
  echo "ERROR: $KEY is a legacy row derived from the FM-1 core experiments; not re-runnable via this driver." >&2
  exit 1
fi
if [ "$PROVIDER" = "anthropic" ] && [ "$PHASE" != "row" ]; then
  echo "ERROR: Anthropic rows use the dedicated runner (scripts/run_bench_anthropic_direct.py," >&2
  echo "       one-shot, not phase-driven; see BM1c adapter notes). Only 'row' works here." >&2
  exit 1
fi
BASE=("$PY" "$HERE/scripts/run_bench_model.py" --provider "$PROVIDER" --model "$KEY")
TIER_FLAGS=()
case "$TIER" in
  reduced)   TIER_FLAGS+=(--windows-only --reps 1 --lap-reps 10) ;;
  full-1rep) TIER_FLAGS+=(--reps 1) ;;
esac
[ "$PROVIDER" = "remote" ] && TIER_FLAGS+=(--arm-max-tokens 8192)

run() {
  if [ "${DRY_RUN:-0}" = "1" ]; then echo "DRY: $*"; else "$@"; fi
}

case "$PHASE" in
  smoke)
    run "${BASE[@]}" --smoke "${TIER_FLAGS[@]}"
    echo ">>> smoke done — MANUALLY INSPECT outputs/bench/$KEY before running 'all' (prereg gate)"
    ;;
  arms)
    run "${BASE[@]}" --job arms "${TIER_FLAGS[@]}"
    ;;
  probes)
    run "${BASE[@]}" --job probes "${TIER_FLAGS[@]}"
    ;;
  row)
    run "$PY" "$HERE/scripts/analyze_bench_row.py" --model "$KEY"
    run "$PY" "$HERE/scripts/make_bench_rows.py"
    echo ">>> row + leaderboard regenerated; add display metadata to scripts/bench_registry.py if this is a new model"
    ;;
  all)
    if [ "${DRY_RUN:-0}" != "1" ] && ! ls "$HERE/outputs/bench/$KEY"/*/rep1/2008-10-15 > /dev/null 2>&1; then
      echo "ERROR: no smoke cells found for $KEY — run 'smoke' and inspect first (prereg gate)" >&2
      exit 1
    fi
    run "${BASE[@]}" --job arms "${TIER_FLAGS[@]}"
    run "${BASE[@]}" --job probes "${TIER_FLAGS[@]}"
    run "$PY" "$HERE/scripts/analyze_bench_row.py" --model "$KEY"
    run "$PY" "$HERE/scripts/make_bench_rows.py"
    ;;
  *)
    echo "unknown phase: $PHASE" >&2; exit 1 ;;
esac
