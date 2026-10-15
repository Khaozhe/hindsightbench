#!/usr/bin/env bash
# Addendum I: the preregistered one resume pass (prereg/BM2c_note_retry.md: "any later rung below 100%
# compliance, one pass, no more") for I7 (3 failed cells, two of them calm-window M cells, which gate E2/E3)
# and I2 (8 cells truncated at arm_max_tokens). Same serving configuration as their first pass (TP=4).
# The runner regenerates only cells without a valid-sketch file; completed cells are never touched.
# Waits until the remainder chain (bm2c_chainI_rest.sh) has released the GPUs.
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/bm2c_logs}"
log() { echo "[$(date '+%F %T')] chainI_resume: $*"; }
while pgrep -f "bm2c_chainI_rest[.]sh" > /dev/null; do sleep 60; done
for r in I7 I2; do
  until [ -f "$HOME/hindsight_models/$(bash "$HERE/scripts/bm2c_ladder.sh" "$r" key)/.download_ok" ]; do sleep 60; done
  log "resume pass $r"
  TP=4 bash "$HERE/scripts/bm2c_ladder.sh" "$r" full > "$LOG_DIR/$r.retry.driver.log" 2>&1; rc=$?
  if [ $rc -eq 0 ]; then echo "RETRIED-OK $r" >> "$LOG_DIR/ladder.progress"; else log "WARN: resume pass $r exited $rc"; fi
done
log "CHAINI_RESUME_END"
