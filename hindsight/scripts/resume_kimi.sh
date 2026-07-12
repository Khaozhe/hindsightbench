#!/bin/bash
# Kimi K2.6 直连续跑链：arms 幂等续 -> 探针 -> 出行（2026-07-06 重写）
# 教训：链式日志禁止 tail 截断（stderr 的 REC_ERROR 曾被 | tail -2 销毁）——全量落盘
P=/opt/homebrew/Caskroom/miniconda/base/envs/macrochain/bin/python
cd REPO_ROOT
LOG=hindsight/outputs/bench/kimi-k2.6/resume_kimi.log
{
  $P hindsight/scripts/run_bench_model.py --provider kimi --model kimi-k2.6 --job arms --reps 2 --concurrency 100
  $P hindsight/scripts/run_bench_model.py --provider kimi --model kimi-k2.6 --job probes --lap-reps 20 --concurrency 100
  $P hindsight/scripts/analyze_bench_row.py --model kimi-k2.6
  echo "RESUME_KIMI_EXIT=$?"
} > "$LOG" 2>&1
tail -5 "$LOG"
