#!/usr/bin/env bash
# Copy the repo files the BM-2c driver needs to a box (run ON the Mac; the Mac is the origin of these files, not a relay).
#   bash hindsight/scripts/bm2c_push_repo.sh <ssh-host-or-alias> [remote-repo-dir]   (default REPO_ROOT)
#   e.g. bash hindsight/scripts/bm2c_push_repo.sh a100-wbx '~/Macro-chain'
set -euo pipefail
HOST="${1:?ssh host or alias}"; RDIR="${2:-REPO_ROOT}"; R=REPO_ROOT
cd "$R"
COPYFILE_DISABLE=1 tar --no-xattrs -czf - hindsight/scripts hindsight/prereg hindsight/models.yaml hindsight/outputs/kt1/masked_nodes hindsight/outputs/fm1c/postcutoff_snapshots.json \
  macrochain/data/processed/spx_target_new.parquet macrochain/data/processed/sketches_panel.jsonl macrochain/data/processed/sketch_batch_requests.jsonl \
  | ssh "$HOST" "mkdir -p $RDIR && tar xzf - -C $RDIR && mkdir -p $RDIR/hindsight/outputs/bench && echo \"pushed: \$(ls $RDIR/hindsight/scripts | wc -l) scripts\""
