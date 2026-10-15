#!/bin/bash
# full ST-1 row: arms -> lap -> rec -> analyze (each job resumable)
set -u
P=${1:-deepseek}; M=${2:-deepseek-v4-flash}; TAG=${M##*/}
cd "$(dirname "$0")"
LOG=../outputs/st1/$TAG/row.log
mkdir -p ../outputs/st1/$TAG
{
  echo "=== $(date -Iseconds) start $P/$M"
  python3 run_st1.py --provider $P --model $M --job arms --concurrency 48
  python3 run_st1.py --provider $P --model $M --job arms --concurrency 24   # second pass picks up transient errors
  python3 run_st1.py --provider $P --model $M --job lap  --concurrency 64
  python3 run_st1.py --provider $P --model $M --job rec  --concurrency 32
  python3 analyze_st1.py --tag $TAG
  echo "=== $(date -Iseconds) done"
} >> $LOG 2>&1
