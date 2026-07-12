#!/usr/bin/env python
"""FM-2: feed FM-1 R/M arm sketches (rep1) through the frozen V1 pipeline
with outputs redirected per arm (prereg: FM2_prereg.md, sha256 deb018b9...).

Usage:
  python run_fm2_pipeline.py --arm M --start 2024-11-15 --end 2024-12-15  # smoke
  python run_fm2_pipeline.py --arm R                                       # full
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hindsight_paths import REPO
MACRO = REPO / "macrochain"
FM1_FLASH = REPO / "hindsight/outputs/fm1/gemini-2.5-flash"
FM2 = REPO / "hindsight/outputs/fm2"

sys.path.insert(0, str(MACRO))
sys.path.insert(0, str(MACRO / "scripts"))


def build_sketch_panel(arm: str, out_path: Path) -> int:
    """FM-1 arm rep1 node dirs -> V1 sketches_panel.jsonl format."""
    n = 0
    with out_path.open("w") as f:
        for node in sorted((FM1_FLASH / arm / "rep1").iterdir()):
            fj = node / "01_sketches_valid.json"
            if not fj.exists():
                continue
            for s in json.loads(fj.read_text()):
                s["decision_date"] = node.name  # caller-injected, as in V1
                f.write(json.dumps(s) + "\n")
                n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["R", "M"], required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    args = ap.parse_args()

    workdir = FM2 / args.arm
    workdir.mkdir(parents=True, exist_ok=True)
    sketches = workdir / "sketches_panel.jsonl"
    n = build_sketch_panel(args.arm, sketches)
    print(f"arm {args.arm}: {n} sketches -> {sketches}")

    import run_full_pipeline as pipe

    # redirect ALL output constants into the arm workdir; inputs stay read-only
    pipe.SKETCHES_PATH = sketches
    pipe.COMPILED_PATH = workdir / "compiled_hypotheses_panel.jsonl"
    pipe.REJECT_PATH = workdir / "compile_reject_log.jsonl"
    pipe.L1_PATH = workdir / "l1_survivors.jsonl"
    pipe.L3_PATH = workdir / "l3_results.jsonl"
    pipe.SCORES_PATH = workdir / "chain_scores.parquet"
    pipe.HSTAR_PATH = workdir / "H_star_panel.jsonl"
    pipe.VVR_PATH = workdir / "vintage_vs_revised_real.parquet"

    argv = ["run_full_pipeline.py"]
    if args.start:
        argv += ["--start", args.start]
    if args.end:
        argv += ["--end", args.end]
    sys.argv = argv
    rc = pipe.main()
    print(f"pipeline rc={rc}")
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
