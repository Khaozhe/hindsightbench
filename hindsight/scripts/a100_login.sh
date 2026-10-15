#!/usr/bin/env bash
# Log into the wbx A100 cluster (account zdhs0037 via the aliyun jump host; keys and Host entries in ~/.ssh/config).
#   bash scripts/a100_login.sh          # interactive shell on the login node (sn02, no GPU)
#   bash scripts/a100_login.sh node     # interactive shell inside the running Slurm allocation (4 x A100-40G)
#   bash scripts/a100_login.sh node 'cmd'   # run one command inside the allocation
# The allocation id is looked up with squeue each time (the placeholder job holding the 4 GPUs).
set -euo pipefail
if [ "${1:-}" = node ]; then
  shift
  ssh -t a100-wbx 'jid=$(squeue -u $USER -h -o "%i %b" | awk "/gpu/{print \$1; exit}"); [ -n "$jid" ] || { echo "no running GPU job"; exit 1; }; echo "allocation $jid on $(squeue -j $jid -h -o %N)"; srun --jobid=$jid --overlap -N1 -n1 --pty bash -ic '"'"'"$@"'"'"' _ '"$*"
else
  ssh a100-wbx
fi
