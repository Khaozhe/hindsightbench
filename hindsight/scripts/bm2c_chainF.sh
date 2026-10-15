#!/usr/bin/env bash
# BM-2c chain F (addendum F, frozen 2026-09-15): runs the rungs given in RUNGS on a fresh box,
# prefetching the next rung's weights while the current one computes, deleting each rung's
# weights after its row (KEEP_WEIGHTS unset). Two boxes run two instances in parallel:
#   2 x 80 GB, TP=2:  RUNGS="T1 T2 T3 F2" TP=2 CONC=16 bash scripts/bm2c_chainF.sh
#   1 x 80 GB:        RUNGS="F1 F3"       CONC=16 bash scripts/bm2c_chainF.sh
# Detach: nohup ... > /root/bm2c_logs/chainF.log 2>&1 & disown.  Ends with CHAINF_END.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-/root/bm2c_logs}"; mkdir -p "$LOG_DIR"
export HINDSIGHT_PY="${HINDSIGHT_PY:-/root/miniconda3/bin/python}" PATH="/root/miniconda3/bin:$PATH" GATE_OVERRIDE=auto CONC="${CONC:-16}"
[ -n "${TP:-}" ] && export TP
RUNGS="${RUNGS:?space-separated rungs}"
log() { echo "[$(date '+%F %T')] chainF: $*"; }
# prefetch loop (sequential, one rung ahead is enough on a 500 GB disk): downloads every rung in order.
# PREFETCH=0 skips it (cluster mode: the compute node has no internet, so the same loop is started
# separately on the login node with `bash bm2c_chainF.sh prefetch`; the rung loop waits on .download_ok).
MODELS_DIR="${MODELS_DIR:-/root/autodl-tmp/models}"
if [ "${1:-}" = prefetch ]; then
  for r in $RUNGS; do bash "$HERE/scripts/bm2c_ladder.sh" "$r" download > "$LOG_DIR/$r.prefetch.log" 2>&1 || log "WARN: prefetch $r failed"; done
  log "PREFETCH_END"; exit 0
fi
if [ "${PREFETCH:-1}" = 1 ]; then
  ( for r in $RUNGS; do bash "$HERE/scripts/bm2c_ladder.sh" "$r" download > "$LOG_DIR/$r.prefetch.log" 2>&1 || log "WARN: prefetch $r failed (driver will retry the download itself)"; done ) &
fi
for r in $RUNGS; do
  if grep -q "RUNG_DONE $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then log "$r already done; skipping"; continue; fi
  key=$(bash "$HERE/scripts/bm2c_ladder.sh" "$r" key)
  until [ -f "$MODELS_DIR/$key/.download_ok" ]; do sleep 60; done
  log "starting $r (auto pre-screen, manual inspection post hoc)"
  bash "$HERE/scripts/bm2c_ladder.sh" "$r" smoke > "$LOG_DIR/$r.driver.log" 2>&1; rc=$?
  if [ $rc -ne 0 ] || ! grep -q "RUNG_DONE $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then log "ABORT: $r exited $rc without RUNG_DONE — see $LOG_DIR/$r.driver.log"; exit 1; fi
  log "$r done"
done
wait
log "CHAINF_END"
