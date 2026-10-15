#!/usr/bin/env bash
# BM-2c unattended tail: waits for the first chain to end (it stops at C's smoke), then runs
# C and ladder B with GATE_OVERRIDE=auto (BM2c_note_unattended.md). Survives operator disconnects.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-/root/bm2c_logs}"
export HINDSIGHT_PY="${HINDSIGHT_PY:-/root/miniconda3/bin/python}" PATH="/root/miniconda3/bin:$PATH" GATE_OVERRIDE=auto
log() { echo "[$(date '+%F %T')] chain2: $*"; }
# WAIT_RUNG (optional): wait for this rung's RUNG_DONE instead of chain 1's end
if [ -n "${WAIT_RUNG:-}" ]; then
  until grep -q "RUNG_DONE ${WAIT_RUNG}\$" "$LOG_DIR/ladder.progress" 2>/dev/null; do sleep 60; done
else
  until grep -q "CHAIN_END" "$LOG_DIR/chain.log" 2>/dev/null; do sleep 60; done
  if grep -q "ABORT" "$LOG_DIR/chain.log"; then log "chain 1 aborted — not continuing"; exit 1; fi
fi
# Resume pass (BM2c_note_retry.md): every ladder-A rung whose output dir holds parse-failed
# cells gets exactly one `full` re-run before C; detected at run time, not hand-listed.
OUT="$HERE/outputs/bench"
RETRY=""
for pair in "A1:olmo3-7b-sft" "A2:olmo3-7b-dpo" "A3:olmo3-7b-instruct" "A3x:olmo3-7b-instruct-guided" "A4:olmo3-7b-think" "A0:olmo3-7b-base-guided"; do
  r="${pair%%:*}"; k="${pair##*:}"
  if [ -d "$OUT/$k" ] && [ -n "$(find "$OUT/$k" -name 99_parse_error.txt -print -quit)" ] && ! grep -q "RETRIED-OK $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then RETRY="$RETRY $r"; fi
done
log "resume pass for:${RETRY:- (none)}"
for r in $RETRY; do
  log "resume pass $r"
  bash "$HERE/scripts/bm2c_ladder.sh" "$r" full > "$LOG_DIR/$r.retry.driver.log" 2>&1; rc=$?
  if [ $rc -eq 0 ]; then echo "RETRIED-OK $r" >> "$LOG_DIR/ladder.progress"; else log "WARN: resume pass $r exited $rc (see $LOG_DIR/$r.retry.driver.log); continuing"; fi
done
for r in ${RUNGS:-C B0 B1 B2 B3 B3x}; do
  while pgrep -f "bm2c_ladder.sh $r download" > /dev/null; do sleep 30; done
  log "starting $r (auto pre-screen, manual inspection post hoc)"
  bash "$HERE/scripts/bm2c_ladder.sh" "$r" smoke > "$LOG_DIR/$r.driver.log" 2>&1; rc=$?
  if [ $rc -ne 0 ] || ! grep -q "RUNG_DONE $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then
    log "ABORT: $r exited $rc without RUNG_DONE — see $LOG_DIR/$r.driver.log"; exit 1
  fi
  log "$r done"
done
log "${CHAIN_TAG:-CHAIN2}_END"
