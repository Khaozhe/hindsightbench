#!/usr/bin/env bash
# BM-2c chain 6: control E (addendum E, frozen 2026-09-14) after chain 6 ends.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-/root/bm2c_logs}"
export HINDSIGHT_PY="${HINDSIGHT_PY:-/root/miniconda3/bin/python}" PATH="/root/miniconda3/bin:$PATH" GATE_OVERRIDE=auto CONC="${CONC:-16}"
log() { echo "[$(date '+%F %T')] chain7: $*"; }
until grep -q "CHAIN6_END" "$LOG_DIR/chain6.log" 2>/dev/null; do sleep 60; done
for r in E1; do
  while pgrep -f "bm2c_ladder.sh $r download" > /dev/null; do sleep 30; done
  log "starting $r (auto pre-screen, manual inspection post hoc)"
  bash "$HERE/scripts/bm2c_ladder.sh" "$r" smoke > "$LOG_DIR/$r.driver.log" 2>&1; rc=$?
  if [ $rc -ne 0 ] || ! grep -q "RUNG_DONE $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then log "ABORT: $r exited $rc without RUNG_DONE — see $LOG_DIR/$r.driver.log"; exit 1; fi
  log "$r done"
done
log "CHAIN7_END"
