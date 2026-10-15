#!/usr/bin/env bash
# Bootstrap a fresh AutoDL box for the BM-2c driver (run ON the box after the repo mirror is copied).
# Mirrors what the wave-4 H800 had: aria2c, vLLM 0.29 in /root/miniconda3 (tsinghua index), hf-mirror.
# Usage: bash REPO_ROOT/hindsight/scripts/bm2c_bootstrap_box.sh
set -euo pipefail
LOG_DIR=/root/bm2c_logs; mkdir -p "$LOG_DIR" /root/autodl-tmp/models
PY=/root/miniconda3/bin/python
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
df -h /root/autodl-tmp | tail -1
if ! command -v aria2c > /dev/null; then apt-get update > "$LOG_DIR/apt_aria2.log" 2>&1 && apt-get install -y aria2 >> "$LOG_DIR/apt_aria2.log" 2>&1; fi
aria2c --version | head -1
if ! "$PY" -c "import vllm; print('vllm', vllm.__version__)" 2>/dev/null; then
  "$PY" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "vllm==0.29.0" httpx pandas pyarrow numpy pyyaml > "$LOG_DIR/pip_install.log" 2>&1
fi
"$PY" -c "import vllm, torch, httpx, pandas, pyarrow, yaml; print('vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'gpus', torch.cuda.device_count())"
command -v ninja || ls /root/miniconda3/bin/ninja
curl -s --max-time 20 -o /dev/null -w "hf-mirror HTTP %{http_code}\n" https://hf-mirror.com/api/models/allenai/Llama-3.1-Tulu-3-70B
echo BOOTSTRAP_OK
