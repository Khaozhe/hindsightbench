#!/usr/bin/env bash
# BM-2c ladder driver — runs ON the GPU box (prereg BM2c_prereg_olmo_ladder.md, afa19e6d).
#
# One rung at a time on a 50 GB data disk: download -> serve -> smoke -> (gate) ->
# arms -> probes -> row -> stop serve -> delete weights. Idempotent: every phase
# resumes from what is on disk (run_bench_model.py / run_bm2b_stage2.py skip done cells).
#
#   bash bm2c_ladder.sh <rung> smoke     # download+serve+smoke, then exit for inspection
#   bash bm2c_ladder.sh <rung> full      # (smoke cells must exist) arms -> probes -> row -> cleanup
#   bash bm2c_ladder.sh <rung> download  # prefetch weights only (no GPU use)
#   bash bm2c_ladder.sh <rung> serve     # just (re)start the server for this rung
#   bash bm2c_ladder.sh <rung> stop      # stop the server (pidfile, never pkill -f)
#
# Rungs: A0 A1 A2 A3 A3x A4 C   (A0 base and A3x released-Instruct both run the guided zero-shot
# completion regime of the BM-2c addendum; the 2-shot regime is kept for reference only)
#
# Conventions (llm_batch_ops): full logs, no `| tail`; server detached with nohup+disown;
# pidfile-based stop; free-disk assertion before every download; HF commit sha recorded.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"          # hindsight/
PY="${HINDSIGHT_PY:-python3}"
MODELS_DIR="${MODELS_DIR:-/root/autodl-tmp/models}"
LOG_DIR="${LOG_DIR:-/root/bm2c_logs}"
PORT="${VLLM_PORT:-8000}"
export REMOTE_VLLM_URL="http://localhost:${PORT}/v1"
mkdir -p "$MODELS_DIR" "$LOG_DIR"

RUNG="${1:?rung A0|A1|A2|A3|A3x|A4|C|B0|B1|B2|B3|B3x|D1|D2|E1|T1|T2|T3|F1|F2|F3|H1|H2|I1|I2|I3|I4|I5|I6|I7|J1|J2|J3}"
PHASE="${2:?phase download|smoke|full|serve|stop|key}"

# rung -> repo | key | regime | dtype/quant | arm_max_tokens | size GB | smoke gate
case "$RUNG" in
  A0)  REPO=allenai/Olmo-3-1025-7B;               KEY=olmo3-7b-base;     REGIME=guided;  QUANT=bf16; AMT=8192;  SIZE=15; GATE=manual ;;
  A1)  REPO=allenai/Olmo-3-7B-Instruct-SFT;       KEY=olmo3-7b-sft;      REGIME=chat;       QUANT=bf16; AMT=8192;  SIZE=15; GATE=manual ;;
  A2)  REPO=allenai/Olmo-3-7B-Instruct-DPO;       KEY=olmo3-7b-dpo;      REGIME=chat;       QUANT=bf16; AMT=8192;  SIZE=30; GATE=auto ;;
  A3)  REPO=allenai/Olmo-3-7B-Instruct;           KEY=olmo3-7b-instruct; REGIME=chat;       QUANT=bf16; AMT=8192;  SIZE=15; GATE=auto ;;
  A3x) REPO=allenai/Olmo-3-7B-Instruct;           KEY=olmo3-7b-instruct; REGIME=guided;  QUANT=bf16; AMT=8192;  SIZE=15; GATE=auto ;;
  A4)  REPO=allenai/Olmo-3-7B-Think;              KEY=olmo3-7b-think;    REGIME=chat;       QUANT=bf16; AMT=16384; SIZE=15; GATE=auto ;;
  C)   REPO=casperhansen/llama-3.3-70b-instruct-awq; KEY=llama-3.3-70b-awq; REGIME=chat;    QUANT=awq;  AMT=8192;  SIZE=40; GATE=manual ;;
  # Ladder B (32B, BF16 throughout; 64.5 GB per rung). B0/B1 manual (first guided + first chat
  # at the new size), B2/B3/B3x automatic, mirroring ladder A — see BM2c_note_B_gates.md.
  B0)  REPO=allenai/Olmo-3-1125-32B;              KEY=olmo3-32b-base;      REGIME=guided;  QUANT=bf16; AMT=8192; SIZE=65; GATE=manual ;;
  B1)  REPO=allenai/Olmo-3.1-32B-Instruct-SFT;    KEY=olmo3.1-32b-sft;     REGIME=chat;    QUANT=bf16; AMT=8192; SIZE=65; GATE=manual ;;
  B2)  REPO=allenai/Olmo-3.1-32B-Instruct-DPO;    KEY=olmo3.1-32b-dpo;     REGIME=chat;    QUANT=bf16; AMT=8192; SIZE=65; GATE=auto ;;
  B3)  REPO=allenai/Olmo-3.1-32B-Instruct;        KEY=olmo3.1-32b-instruct; REGIME=chat;   QUANT=bf16; AMT=8192; SIZE=65; GATE=auto ;;
  B3x) REPO=allenai/Olmo-3.1-32B-Instruct;        KEY=olmo3.1-32b-instruct; REGIME=guided; QUANT=bf16; AMT=8192; SIZE=65; GATE=auto ;;
  # Control D (BM2c_addendum_D_qwen2507.md): second fixed-corpus recipe contrast, paired with
  # benchmark row 15 (qwen3-30b-a3b-fp8dyn: vLLM dynamic FP8, 1 rep, temp 0.2).
  D1)  REPO=Qwen/Qwen3-30B-A3B-Instruct-2507;      KEY=qwen3-30b-a3b-instruct-2507-fp8dyn; REGIME=chat; QUANT=fp8dyn; AMT=8192;  SIZE=61; GATE=manual ;;
  D2)  REPO=Qwen/Qwen3-30B-A3B-Thinking-2507;      KEY=qwen3-30b-a3b-thinking-2507-fp8dyn; REGIME=chat; QUANT=fp8dyn; AMT=16384; SIZE=61; GATE=manual ;;
  # Control E (BM2c_addendum_E_nemotron.md): one RLHF stage on Llama-3.1-70B-Instruct, AWQ-INT4 as control C.
  E1)  REPO=ibnzterrell/Nvidia-Llama-3.1-Nemotron-70B-Instruct-HF-AWQ-INT4; KEY=llama-3.1-nemotron-70b-awq; REGIME=chat; QUANT=awq; AMT=8192; SIZE=40; GATE=manual ;;
  # Addendum F (BM2c_addendum_F_llama_recipe_panel.md): recipe panel + Tulu stage ladder on the Llama 3.1 70B base.
  # T1-T3 and F2 need TP=2 (set TP=2 in the environment); fp8dyn = BF16 weights quantised at load, fp8 = official FP8 checkpoint.
  T1)  REPO=allenai/Llama-3.1-Tulu-3-70B-SFT;         KEY=tulu3-70b-sft-fp8dyn;      REGIME=chat; QUANT=fp8dyn; AMT=8192;  SIZE=141; GATE=manual ;;
  T2)  REPO=allenai/Llama-3.1-Tulu-3-70B-DPO;         KEY=tulu3-70b-dpo-fp8dyn;      REGIME=chat; QUANT=fp8dyn; AMT=8192;  SIZE=141; GATE=auto ;;
  T3)  REPO=allenai/Llama-3.1-Tulu-3-70B;             KEY=tulu3-70b-rlvr-fp8dyn;     REGIME=chat; QUANT=fp8dyn; AMT=8192;  SIZE=141; GATE=auto ;;
  F1)  REPO=casperhansen/deepseek-r1-distill-llama-70b-awq; KEY=r1-distill-llama-70b-awq; REGIME=chat; QUANT=awq; AMT=16384; SIZE=40; GATE=manual ;;
  F2)  REPO=NousResearch/Hermes-3-Llama-3.1-70B-FP8;  KEY=hermes3-70b-fp8;           REGIME=chat; QUANT=fp8;    AMT=8192;  SIZE=71;  GATE=manual ;;
  # Addendum I (BM2c_addendum_I_dose.md): precision dose-response on Qwen3-30B-A3B-Thinking-2507, one A100 box, TP=4.
  I1)  REPO=Qwen/Qwen3-30B-A3B-Thinking-2507;          KEY=qwen3-30b-a3b-thinking-2507-bf16;     REGIME=chat; QUANT=bf16;       AMT=16384; SIZE=62; GATE=manual ;;
  I2)  REPO=QuantTrio/Qwen3-30B-A3B-Thinking-2507-AWQ; KEY=qwen3-30b-a3b-thinking-2507-awq;      REGIME=chat; QUANT=awqbf16;    AMT=16384; SIZE=17; GATE=manual; TPL_FROM=Qwen/Qwen3-30B-A3B-Thinking-2507 ;;
  I3)  REPO=Qwen/Qwen3-30B-A3B-Thinking-2507;          KEY=qwen3-30b-a3b-thinking-2507-bf16-r2;  REGIME=chat; QUANT=bf16;       AMT=16384; SIZE=62; GATE=auto ;;
  I4)  REPO=RedHatAI/Qwen3-30B-A3B-Thinking-2507-quantized.w4a16; KEY=qwen3-30b-a3b-thinking-2507-gptq-w4a16; REGIME=chat; QUANT=auto; AMT=16384; SIZE=17; GATE=auto ;;
  I5)  REPO=RedHatAI/Qwen3-30B-A3B-Thinking-2507-quantized.w8a8;  KEY=qwen3-30b-a3b-thinking-2507-int8-w8a8;  REGIME=chat; QUANT=auto; AMT=16384; SIZE=32; GATE=auto ;;
  I6)  REPO=Qwen/Qwen3-30B-A3B-Thinking-2507-FP8;      KEY=qwen3-30b-a3b-thinking-2507-fp8block; REGIME=chat; QUANT=auto;       AMT=16384; SIZE=32; GATE=auto ;;
  I7)  REPO=Qwen/Qwen3-30B-A3B-Thinking-2507;          KEY=qwen3-30b-a3b-thinking-2507-bf16-fp16act; REGIME=chat; QUANT=bf16asfp16; AMT=16384; SIZE=62; GATE=auto ;;
  # Addendum H (BM2c_addendum_H_tier.md): control C re-measured in the FP8 tier (TP=4 on A100).
  H1)  REPO=unsloth/Llama-3.3-70B-Instruct;           KEY=llama-3.3-70b-fp8dyn;      REGIME=chat; QUANT=fp8dyn; AMT=8192;  SIZE=141; GATE=manual ;;
  H2)  REPO=unsloth/Meta-Llama-3.1-70B-Instruct;      KEY=llama-3.1-70b-fp8dyn;      REGIME=chat; QUANT=fp8dyn; AMT=8192;  SIZE=141; GATE=auto ;;
  F3)  REPO=Valdemardi/Llama-3.1-Tulu-3-70B-AWQ;      KEY=tulu3-70b-rlvr-awq;        REGIME=chat; QUANT=awq;    AMT=8192;  SIZE=40;  GATE=auto ;;
  # Addendum J (BM2c_addendum_J_tier_split.md): Tulu 3 70B RLVR tier split, TP=4, CONC 16, same box as T3/F3.
  # WKEY = weights directory shared between rungs; EXPECT_SHA = the revision T3/F3 used (download refuses any other).
  J1)  REPO=Valdemardi/Llama-3.1-Tulu-3-70B-AWQ;      KEY=tulu3-70b-rlvr-awq-bf16act; WKEY=tulu3-70b-rlvr-awq;    REGIME=chat; QUANT=awqbf16; AMT=8192; SIZE=40;  GATE=auto; EXPECT_SHA=782516fd513d256c399ee7f4eab3be6b399683e5 ;;
  J2)  REPO=allenai/Llama-3.1-Tulu-3-70B;             KEY=tulu3-70b-rlvr-fp8dyn-r2;   WKEY=tulu3-70b-rlvr-fp8dyn; REGIME=chat; QUANT=fp8dyn;  AMT=8192; SIZE=141; GATE=auto; EXPECT_SHA=cfc1d855e534a0b9b82a9cea6bf9e8dda30b10d7 ;;
  J3)  REPO=Valdemardi/Llama-3.1-Tulu-3-70B-AWQ;      KEY=tulu3-70b-rlvr-awq-r2;      WKEY=tulu3-70b-rlvr-awq;    REGIME=chat; QUANT=awq;     AMT=8192; SIZE=40;  GATE=auto; EXPECT_SHA=782516fd513d256c399ee7f4eab3be6b399683e5 ;;
  *) echo "unknown rung $RUNG" >&2; exit 2 ;;
esac
# Unattended override (BM2c_note_unattended.md): manual gates become automatic pre-screens;
# manual inspection is done post hoc on the archived smoke cells.
[ "${GATE_OVERRIDE:-}" = auto ] && GATE=auto
MDIR="$MODELS_DIR/${WKEY:-$KEY}"
PIDF="$LOG_DIR/$KEY.serve.pid"
SLOG="$LOG_DIR/$KEY.serve.log"
OUT="$HERE/outputs/bench"
case "$REGIME" in
  base2shot) OUTNAME="${KEY}-2shot" ;;
  guided)    OUTNAME="${KEY}-guided" ;;
  inst2shot) OUTNAME="${KEY}-2shot" ;;
  chat)      OUTNAME="$KEY" ;;
esac

log() { echo "[$(date '+%F %T')] $*"; }

write_rev() {   # hf_revision.json for this rung's output dir (also when the weights were shared with another rung)
  mkdir -p "$OUT/$OUTNAME"
  "$PY" - "$REPO" "$1" "$QUANT" "$OUT/$OUTNAME/hf_revision.json" <<'PYR'
import sys, json, datetime
repo, sha, quant, out = sys.argv[1:]
json.dump({"repo": repo, "hf_commit_sha": sha, "quant": quant, "prereg": "BM2c_prereg_olmo_ladder.md afa19e6d",
           "downloaded_at": datetime.datetime.now().isoformat(timespec="seconds")}, open(out, "w"), indent=2)
PYR
}

download() {
  if [ -f "$MDIR/.download_ok" ]; then
    log "weights present: $MDIR"
    if [ ! -f "$OUT/$OUTNAME/hf_revision.json" ] && [ -f "$MDIR/.hf_api.json" ]; then
      write_rev "$("$PY" -c 'import sys,json;print(json.load(open(sys.argv[1])).get("sha",""))' "$MDIR/.hf_api.json")"
    fi
    return
  fi
  free_gb=$(df -BG --output=avail "$MODELS_DIR" | tail -1 | tr -dc '0-9')
  need=$(( SIZE * 11 / 10 + 2 ))
  [ "$free_gb" -ge "$need" ] || { echo "FAIL: need ${need}G free on $MODELS_DIR, have ${free_gb}G — delete a finished rung first" >&2; exit 3; }
  mkdir -p "$MDIR"
  # File list + sizes + commit sha from the HF API via hf-mirror (the AutoDL proxy path to
  # huggingface.co throttled to ~50 KB/s on the last shards, 2026-09-13); safetensors shards
  # go through aria2c -x16 (~17 MB/s aggregate measured), small files through curl.
  MIRROR="${HF_MIRROR:-https://hf-mirror.com}"
  curl -s --max-time 60 "$MIRROR/api/models/$REPO?blobs=true" > "$MDIR/.hf_api.json" || { echo "FAIL: HF API via $MIRROR" >&2; exit 3; }
  sha=$("$PY" -c 'import sys,json;print(json.load(open(sys.argv[1])).get("sha",""))' "$MDIR/.hf_api.json")
  if [ -n "${EXPECT_SHA:-}" ] && [ "$sha" != "$EXPECT_SHA" ]; then echo "FAIL: $REPO is at $sha, the frozen revision is $EXPECT_SHA" >&2; exit 3; fi
  log "downloading $REPO (sha $sha) -> $MDIR (${SIZE}G) via $MIRROR"
  "$PY" - "$MDIR/.hf_api.json" > "$MDIR/.files.tsv" <<'PYF'
import sys, json
d = json.load(open(sys.argv[1]))
skip = (".bin", ".pt", ".gguf")
for s in d["siblings"]:
    f = s["rfilename"]
    if f.endswith(skip) or f.startswith(("original/", "consolidated")): continue
    # stray dotfiles in some repos (a vim .swp in Olmo-3-7B-Think, 2026-09-14) are not weights
    if f.rsplit("/", 1)[-1].startswith(".") and f != ".gitattributes": continue
    print(f"{s.get('size', 0)}\t{f}")
PYF
  while IFS=$'\t' read -r sz f; do
    dest="$MDIR/$f"; mkdir -p "$(dirname "$dest")"
    if [ -f "$dest" ] && [ ! -f "$dest.aria2" ] && [ "$(stat -c %s "$dest")" = "$sz" ]; then continue; fi
    if [ "$sz" -gt 100000000 ]; then
      aria2c -x16 -s16 -k8M --file-allocation=none -c -q -d "$(dirname "$dest")" -o "$(basename "$dest")" \
        "$MIRROR/$REPO/resolve/main/$f" >> "$LOG_DIR/$KEY.download.log" 2>&1 || { echo "FAIL: aria2 $f" >&2; exit 3; }
    else
      curl -sL --max-time 300 -o "$dest" "$MIRROR/$REPO/resolve/main/$f" || { echo "FAIL: curl $f" >&2; exit 3; }
    fi
    got=$(stat -c %s "$dest")
    [ "$got" = "$sz" ] || { echo "FAIL: size mismatch $f: got $got want $sz" >&2; exit 3; }
  done < "$MDIR/.files.tsv"
  if [ -n "$(find "$MDIR" -name "*.aria2" -print -quit)" ]; then echo "FAIL: aria2 control files remain in $MDIR" >&2; exit 3; fi
  write_rev "$sha"
  if [ -n "${TPL_FROM:-}" ]; then   # replace the repo's chat template with the reference repo's (backup kept)
    curl -sL --max-time 120 -o "$MDIR/.ref_tokenizer_config.json" "$MIRROR/$TPL_FROM/resolve/main/tokenizer_config.json" || { echo "FAIL: template fetch" >&2; exit 3; }
    "$PY" - "$MDIR" "$TPL_FROM" <<'PYT' || { echo "FAIL: template copy" >&2; exit 3; }
import json, sys, pathlib, hashlib
m, ref = pathlib.Path(sys.argv[1]), sys.argv[2]
tc = m / "tokenizer_config.json"; bak = m / "tokenizer_config.orig.json"
if not bak.exists(): bak.write_text(tc.read_text())
c = json.loads(bak.read_text()); r = json.loads((m / ".ref_tokenizer_config.json").read_text())
c["chat_template"] = r["chat_template"]; tc.write_text(json.dumps(c, indent=2, ensure_ascii=False))
(m / "TEMPLATE_NOTE.txt").write_text(f"chat_template replaced with {ref}'s (sha {hashlib.sha256(r['chat_template'].encode()).hexdigest()[:8]}); original kept in tokenizer_config.orig.json\n")
print("template from", ref, hashlib.sha256(r["chat_template"].encode()).hexdigest()[:8])
PYT
  fi
  touch "$MDIR/.download_ok"
  log "download ok; every file matches its API byte size; hf sha $sha"
}

serve() {
  if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then log "server already up (pid $(cat "$PIDF"))"; return; fi
  qflags=(--dtype bfloat16)
  [ "$QUANT" = awq ] && qflags=(--quantization awq_marlin --dtype float16)
  [ "$QUANT" = fp8dyn ] && qflags=(--quantization fp8 --dtype bfloat16)   # row-15 serving (dynamic FP8 on BF16 weights)
  [ "$QUANT" = fp8 ] && qflags=(--dtype bfloat16)                          # official FP8 checkpoint: vLLM reads the quantization config itself
  [ "$QUANT" = auto ] && qflags=(--dtype bfloat16)                         # pre-quantized repo (compressed-tensors / block FP8): vLLM reads its config
  [ "$QUANT" = awqbf16 ] && qflags=(--quantization awq_marlin --dtype bfloat16)   # AWQ with bf16 activations (addendum I)
  [ "$QUANT" = bf16asfp16 ] && qflags=(--dtype float16)                     # BF16 weights served with fp16 activations (dtype control, addendum I)
  [ -n "${TP:-}" ] && qflags+=(--tensor-parallel-size "$TP")
  # extra serving flags from the environment (space-separated; e.g. a --compilation-config JSON without spaces,
  # or --enforce-eager). Used on the A100 box where vLLM's FP8 fusion pass fails to compile (2026-09-23).
  [ -n "${VLLM_EXTRA_ARGS:-}" ] && read -r -a extra <<< "$VLLM_EXTRA_ARGS" && qflags+=("${extra[@]}")
  log "starting vLLM for $KEY ($QUANT) on :$PORT"
  nohup "$PY" -m vllm.entrypoints.openai.api_server --model "$MDIR" --served-model-name "$KEY" \
      --port "$PORT" --max-model-len 24576 --gpu-memory-utilization 0.92 "${qflags[@]}" \
      > "$SLOG" 2>&1 < /dev/null &
  echo $! > "$PIDF"; disown
  for i in $(seq 1 120); do
    if curl -s --max-time 5 "$REMOTE_VLLM_URL/models" | grep -q "\"$KEY\""; then log "server healthy after ${i}0s"; return; fi
    if ! kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "FAIL: vLLM died, see $SLOG" >&2; exit 4; fi
    sleep 10
  done
  echo "FAIL: vLLM not healthy after 20 min, see $SLOG" >&2; exit 4
}

stop_serve() {
  if [ -f "$PIDF" ]; then
    pid=$(cat "$PIDF"); kill "$pid" 2>/dev/null || true
    for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 2; done
    kill -9 "$pid" 2>/dev/null || true; rm -f "$PIDF"; log "server stopped"
  fi
}

runner() {   # runner <job>  (smoke|arms|probes|lap)
  case "$REGIME" in
    chat)
      case "$1" in
        smoke)  "$PY" "$HERE/scripts/run_bench_model.py" --provider remote --model "$KEY" --smoke --reps 1 --arm-max-tokens "$AMT" ;;
        arms)   "$PY" "$HERE/scripts/run_bench_model.py" --provider remote --model "$KEY" --job arms --reps 1 --arm-max-tokens "$AMT" --concurrency "${CONC:-32}" ;;
        probes) "$PY" "$HERE/scripts/run_bench_model.py" --provider remote --model "$KEY" --job probes --lap-reps 10 --concurrency "${CONC:-32}" ;;
      esac ;;
    base2shot|inst2shot|guided)
      case "$1" in
        smoke)  "$PY" "$HERE/scripts/run_bm2b_stage2.py" --outname "$OUTNAME" --served "$KEY" --job smoke --regime "$( [ "$REGIME" = guided ] && echo guided || echo 2shot )" ;;
        arms)   "$PY" "$HERE/scripts/run_bm2b_stage2.py" --outname "$OUTNAME" --served "$KEY" --job arms --concurrency "${CONC:-32}" --regime "$( [ "$REGIME" = guided ] && echo guided || echo 2shot )" ;;
        probes) "$PY" "$HERE/scripts/run_bm2b_stage2.py" --outname "$OUTNAME" --served "$KEY" --job lap --concurrency "${CONC:-32}" --lap-reps 10 --regime "$( [ "$REGIME" = guided ] && echo guided || echo 2shot )" ;;
      esac ;;
  esac
}

auto_smoke_check() {
  n_ok=$(find "$OUT/$OUTNAME" -name "01_sketches_valid.json" | wc -l | tr -dc '0-9')
  n_valid=$("$PY" - "$OUT/$OUTNAME" <<'PY'
import sys, json, pathlib
n = 0
for f in pathlib.Path(sys.argv[1]).rglob("01_sketches_valid.json"):
    if len(json.load(open(f))) >= 4: n += 1
print(n)
PY
)
  log "auto smoke: $n_ok cells parsed, $n_valid with >=4 valid sketches (gate: >=6 of 8)"
  [ "$n_valid" -ge 6 ] || { echo "FAIL: automatic smoke gate ($n_valid < 6) — inspect $OUT/$OUTNAME and decide manually" >&2; exit 5; }
}

case "$PHASE" in
  key) echo "${WKEY:-$KEY}"; exit 0 ;;   # print the weights key (chain scripts map rung -> weights dir)
  download) download ;;          # prefetch only (disk permitting) while another rung computes
  serve) download; serve ;;
  stop)  stop_serve ;;
  smoke)
    download; serve
    runner smoke > "$LOG_DIR/$KEY.smoke.log" 2>&1
    if [ "$GATE" = manual ]; then
      log "SMOKE DONE — manual inspection required (prereg gate): $OUT/$OUTNAME ; then run: bash $0 $RUNG full"
    else
      auto_smoke_check
      log "auto smoke passed; continuing to full"
      exec bash "$0" "$RUNG" full
    fi ;;
  full)
    # -print -quit: no pipe, so a large output tree cannot SIGPIPE find under pipefail
    # (that false "no smoke cells" fired on the A2/A3/A3x resume passes, 2026-09-14 08:40)
    if [ -z "$(find "$OUT/$OUTNAME" -name "01_sketches_valid.json" -print -quit 2>/dev/null)" ]; then
      echo "FAIL: no smoke cells for $OUTNAME — run 'smoke' first (prereg gate)" >&2; exit 6
    fi
    download; serve
    runner arms   > "$LOG_DIR/$KEY.arms.log"   2>&1
    runner probes > "$LOG_DIR/$KEY.probes.log" 2>&1
    # row for every regime (the analyzer reads the arm/probe layout, which guided runs share;
    # REC absent -> "-" columns), so the box holds finished rows even if the operator is offline
    "$PY" "$HERE/scripts/analyze_bench_row.py" --model "$OUTNAME" > "$LOG_DIR/$OUTNAME.row.log" 2>&1 || log "row analysis failed (see $LOG_DIR/$OUTNAME.row.log) — data kept"
    stop_serve
    if [ "${KEEP_WEIGHTS:-0}" != 1 ]; then
      # A3 and A3x share weights: delete only after both are done
      if [[ "$RUNG" = A3 || "$RUNG" = B3 ]] && [ ! -f "$OUT/${KEY}-guided/lap_probe_results.jsonl" ]; then log "keeping $MDIR for ${RUNG}x";
      elif [[ "$RUNG" = A3x || "$RUNG" = B3x ]] && [ ! -f "$OUT/$KEY/lap_probe_results.jsonl" ]; then log "keeping $MDIR for ${RUNG%x}";
      else rm -rf "$MDIR"; log "weights deleted: $MDIR"; fi
    fi
    log "RUNG_DONE $RUNG $OUTNAME"
    echo "RUNG_DONE $RUNG" >> "$LOG_DIR/ladder.progress" ;;
  *) echo "unknown phase $PHASE" >&2; exit 2 ;;
esac
