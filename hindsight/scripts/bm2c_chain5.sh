#!/usr/bin/env bash
# BM-2c chain 5: one resume pass (BM2c_note_retry.md) for every ladder-B rung whose matrix
# holds parse-failed cells, run after chain 4 ends. Weights are kept across the passes
# (B3 and B3x share one download) and deleted at the end.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-/root/bm2c_logs}"
export HINDSIGHT_PY="${HINDSIGHT_PY:-/root/miniconda3/bin/python}" PATH="/root/miniconda3/bin:$PATH" GATE_OVERRIDE=auto KEEP_WEIGHTS=1 CONC="${CONC:-16}"
log() { echo "[$(date '+%F %T')] chain5: $*"; }
until grep -q "CHAIN4_END" "$LOG_DIR/chain4.log" 2>/dev/null; do sleep 60; done
OUT="$HERE/outputs/bench"; RETRY=""
for pair in "B1:olmo3.1-32b-sft" "B2:olmo3.1-32b-dpo" "B3:olmo3.1-32b-instruct" "B3x:olmo3.1-32b-instruct-guided" "B0:olmo3-32b-base-guided"; do
  r="${pair%%:*}"; k="${pair##*:}"
  if [ -d "$OUT/$k" ] && [ -n "$(find "$OUT/$k" -name 99_parse_error.txt -print -quit)" ] && ! grep -q "RETRIED-OK $r\$" "$LOG_DIR/ladder.progress" 2>/dev/null; then RETRY="$RETRY $r"; fi
done
log "resume pass for:${RETRY:- (none)}"
for r in $RETRY; do
  while pgrep -f "bm2c_ladder.sh $r download" > /dev/null; do sleep 30; done
  log "resume pass $r"
  bash "$HERE/scripts/bm2c_ladder.sh" "$r" full > "$LOG_DIR/$r.retry.driver.log" 2>&1; rc=$?
  if [ $rc -eq 0 ]; then echo "RETRIED-OK $r" >> "$LOG_DIR/ladder.progress"; else log "WARN: resume pass $r exited $rc (see $LOG_DIR/$r.retry.driver.log); continuing"; fi
done
for m in olmo3.1-32b-sft olmo3.1-32b-dpo olmo3.1-32b-instruct olmo3-32b-base; do [ -d "/root/autodl-tmp/models/$m" ] && { rm -rf "/root/autodl-tmp/models/$m"; log "weights deleted: $m"; }; done
log "CHAIN5_END"
