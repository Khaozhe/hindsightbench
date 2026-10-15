#!/usr/bin/env bash
# BM-2c server-side chain: survives the operator's session (nohup + disown at launch).
# Waits for a running rung to finish, then runs the auto-gated rungs back to back and
# stops at the first manual-gate rung (prereg: A0/A1/C manual; A2/A3/A3x/A4 automatic).
#
#   nohup bash bm2c_chain.sh "A1" "A2 A3 A3x A4" "C" > /root/bm2c_logs/chain.log 2>&1 &
#     arg1 = rung whose RUNG_DONE to wait for first (may be empty)
#     arg2 = auto-gated rungs to run in order (smoke -> auto gate -> full, via the driver)
#     arg3 = manual-gate rung to bring up to SMOKE DONE and then stop (may be empty)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-/root/bm2c_logs}"
export HINDSIGHT_PY="${HINDSIGHT_PY:-/root/miniconda3/bin/python}"
export PATH="/root/miniconda3/bin:$PATH"
WAIT_FOR="${1:-}"; AUTO="${2:-}"; MANUAL="${3:-}"
log() { echo "[$(date '+%F %T')] chain: $*"; }

if [ -n "$WAIT_FOR" ]; then
  log "waiting for RUNG_DONE $WAIT_FOR"
  until grep -q "RUNG_DONE $WAIT_FOR\$" "$LOG_DIR/ladder.progress" 2>/dev/null; do
    if grep -q "FAIL" "$LOG_DIR/$WAIT_FOR.full.driver.log" 2>/dev/null; then
      log "ABORT: $WAIT_FOR full driver reported FAIL"; exit 1
    fi
    sleep 60
  done
  log "$WAIT_FOR done"
fi

for r in $AUTO; do
  # weights may still be prefetching (A4 queued behind C): the driver's download() resumes
  # by byte size, but do not race a running prefetch on the same directory
  while pgrep -f "bm2c_ladder.sh $r download" > /dev/null; do sleep 30; done
  log "starting $r (auto gate)"
  bash "$HERE/scripts/bm2c_ladder.sh" "$r" smoke > "$LOG_DIR/$r.driver.log" 2>&1
  rc=$?
  if [ $rc -ne 0 ] || ! grep -q "RUNG_DONE $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then
    log "ABORT: $r exited $rc without RUNG_DONE — see $LOG_DIR/$r.driver.log"; exit 1
  fi
  log "$r done"
done

if [ -n "$MANUAL" ]; then
  while pgrep -f "bm2c_ladder.sh $MANUAL download" > /dev/null; do sleep 30; done
  log "bringing up $MANUAL for manual smoke inspection"
  bash "$HERE/scripts/bm2c_ladder.sh" "$MANUAL" smoke > "$LOG_DIR/$MANUAL.driver.log" 2>&1
  log "$MANUAL smoke phase exited $? — inspect, then: bash scripts/bm2c_ladder.sh $MANUAL full"
fi
log "CHAIN_END"
