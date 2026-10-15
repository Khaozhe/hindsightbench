#!/usr/bin/env bash
# Addendum J (prereg/BM2c_addendum_J_tier_split.md): Tulu 3 70B RLVR tier split on the wbx A100 box.
# Order J1 J3 (share F3's AWQ weights), then J2 (T3's BF16 weights, prefetched on the login node meanwhile).
# Same serving as T3/F3: TP=4, CONC 16. Each rung runs even if another failed (a failed rung is reported
# missing). Weights are kept until the end (shared between rungs). Then the preregistered one resume pass
# (BM2c_note_retry.md) for any rung with fewer than 1,032 valid cells.
HERE="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/bm2c_logs}"; OUT="$HERE/outputs/bench"
export KEEP_WEIGHTS=1 TP=4 CONC=16
log() { echo "[$(date '+%F %T')] chainJ: $*"; }
for r in J1 J3 J2; do RUNGS="$r" bash "$HERE/scripts/bm2c_chainF.sh"; log "stage $r exit $?"; done
for r in J1 J3 J2; do
  k=$(grep -m1 "^  $r)" "$HERE/scripts/bm2c_ladder.sh" | sed 's/.* KEY=\([^;]*\);.*/\1/')
  n=$(find "$OUT/$k" -name 01_sketches_valid.json 2>/dev/null | wc -l | tr -dc '0-9')
  if grep -q "RUNG_DONE $r\$" "$LOG_DIR/ladder.progress" && [ "${n:-0}" -lt 1032 ]; then
    log "resume pass $r ($n/1032 cells)"
    bash "$HERE/scripts/bm2c_ladder.sh" "$r" full > "$LOG_DIR/$r.retry.driver.log" 2>&1 && echo "RETRIED-OK $r" >> "$LOG_DIR/ladder.progress" || log "WARN: resume pass $r failed"
  fi
done
log "CHAINJ_END"
