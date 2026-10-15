#!/usr/bin/env bash
# Addendum-I remainder after the I4 TP=4 failure (prereg/BM2c_note_I_deviation_tp.md, bfe0a729):
# I5 and I7 at the frozen TP=4, then I4 and I6 at TP=2. Each stage continues even if the other fails,
# so one unservable rung cannot block the rest; failures are reported as missing rungs.
HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNGS="I5 I7" TP=4 bash "$HERE/scripts/bm2c_chainF.sh"; echo "stage TP=4 exit $?"
RUNGS="I4" TP=2 bash "$HERE/scripts/bm2c_chainF.sh"; echo "stage I4 TP=2 exit $?"
RUNGS="I6" TP=2 bash "$HERE/scripts/bm2c_chainF.sh"; echo "stage I6 TP=2 exit $?"
echo "chainI_rest: END"
