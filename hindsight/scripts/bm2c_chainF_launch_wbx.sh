#!/usr/bin/env bash
# Launch the addendum-F rung chain inside the running Slurm GPU allocation on the wbx cluster.
# Run ON the login node (sn02). The prefetch loop runs separately on the login node
# (`bash scripts/bm2c_chainF.sh prefetch`, same env); this chain only waits on .download_ok markers.
#   bash scripts/bm2c_chainF_launch_wbx.sh            # start (detached; log ~/bm2c_logs/chainF.log)
#   bash scripts/bm2c_chainF_launch_wbx.sh status     # progress
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/vllm029/bin:$HOME/bin:$PATH" MODELS_DIR="$HOME/hindsight_models" LOG_DIR="$HOME/bm2c_logs" \
       HINDSIGHT_PY="$HOME/vllm029/bin/python" RUNGS="${RUNGS:-F1 T1 T2 T3 F2 F3}" TP="${TP:-4}" CONC="${CONC:-16}" PREFETCH=0 \
       HF_HUB_OFFLINE=1 VLLM_LOGGING_LEVEL=INFO
# CUDA toolkit for torch.compile / inductor (same as `module load cuda/13.0`; matches torch cu130).
# Without nvcc on PATH inductor fails and hides the real error behind PermissionError: 'nvcc' (2026-09-22).
export CUDA_HOME=/data/apps/cuda/13.0 PATH="/data/apps/cuda/13.0/bin:$PATH" LD_LIBRARY_PATH="/data/apps/cuda/13.0/lib64:${LD_LIBRARY_PATH:-}"
# Compile caches on the compute node's local disk: four TP workers racing on one shared-FS Triton
# cache produced "cuda_utils.so: cannot open shared object file" (2026-09-22). /tmp is node-local.
export TRITON_CACHE_DIR="/tmp/$USER/triton_cache" TORCHINDUCTOR_CACHE_DIR="/tmp/$USER/inductor_cache" VLLM_CACHE_ROOT="/tmp/$USER/vllm_cache"
# A100 has no FP8 tensor cores: vLLM 0.29 still picks CutlassFP8ScaledMMLinearKernel for online FP8 and dies
# at profiling (cutlass_scaled_mm_sm80 has no FP8 epilogue). Disabling it selects MarlinFP8 (W8A16), verified 2026-09-23.
export VLLM_DISABLED_KERNELS=CutlassFP8ScaledMMLinearKernel
JID=$(squeue -u "$USER" -h -o "%i %b" | awk '/gpu/{print $1; exit}')
[ -n "$JID" ] || { echo "no running GPU allocation"; exit 1; }
if [ "${1:-}" = status ]; then
  echo "allocation $JID on $(squeue -j "$JID" -h -o %N)"; tail -5 "$LOG_DIR/chainF.log" 2>/dev/null; echo "--- progress"; cat "$LOG_DIR/ladder.progress" 2>/dev/null
  echo "--- downloads"; for d in "$MODELS_DIR"/*/; do printf "%s %s %s\n" "$(basename "$d")" "$(du -sh "$d" | cut -f1)" "$([ -f "$d/.download_ok" ] && echo ok || echo ...)"; done; exit 0
fi
mkdir -p "$LOG_DIR"
CHAIN="${CHAIN:-scripts/bm2c_chainF.sh}"   # override to run another chain script in the same allocation
CHAIN_LOG="${CHAIN_LOG:-chainF.log}"
nohup srun --jobid="$JID" --overlap -N1 -n1 --export=ALL bash "$HERE/$CHAIN" > "$LOG_DIR/$CHAIN_LOG" 2>&1 &
disown; echo "chain launched in allocation $JID (srun pid $!), log $LOG_DIR/chainF.log"
