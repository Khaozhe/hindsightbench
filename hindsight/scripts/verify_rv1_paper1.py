#!/usr/bin/env python3
"""Gate: every RV-1 number printed in paper 1 (main text + appendix E.14) is re-derived from the generated
RV-1 JSONs and WHOLEPANEL_G.md and must appear in the LaTeX, formatted as printed. Also checks that the
RV-1 frozen files still hash to RV1_freeze.json. Exit 1 on any miss.

    python scripts/verify_rv1_paper1.py
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

H = Path(__file__).resolve().parents[1]
R = H / "outputs/review"
SEC = H / "paper/latex/sections"


def norm(s: str) -> str:
    s = s.replace("$-$", "-").replace("−", "-").replace("{[}", "[").replace("{]}", "]")
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    return re.sub(r"\s+", " ", s)


TEX = {f.name: norm(f.read_text()) for f in SEC.glob("*.tex")}
ALL = " ".join(TEX.values())
fails = []


def f1(x):  # signed, one decimal, as printed
    return ("%+.1f" % x).replace("+-", "-")


def ci(c):
    return "[%s, %s]" % (f1(c[0]), f1(c[1]))


def need(s, where=None, label=""):
    hay = TEX[where] if where else ALL
    if s not in hay:
        fails.append(f"{label}: '{s}' not found in {where or 'any section'}")


# freeze hashes
fz = json.loads((H / "prereg/RV1_freeze.json").read_text())
for p, h in fz["sha256"].items():
    if hashlib.sha256((H / p).read_bytes()).hexdigest() != h:
        fails.append(f"freeze: {p} hash mismatch")

ps = json.loads((R / "rv1_preshock.json").read_text())
for m in ("flash", "pro", "deepseek"):
    for st in ("primary", "sens_mild", "sens_severe"):
        r = ps[m][st]
        need(f"{f1(r['PS'])} {ci(r['ci95_date'])}".lstrip("+") if r["PS"] < 0 else f"{f1(r['PS'])} {ci(r['ci95_date'])}",
             "A5_appendix_robustness.tex", f"preshock {m}/{st}")
        need(f"{r['n_shock']}/{r['n_control']}", "A5_appendix_robustness.tex", f"preshock n {m}/{st}")
fl = ps["flash"]["primary"]
for f in ("00_abstract.tex", "01_intro.tex"):
    need(f"{f1(fl['PS'])}pp {ci(fl['ci95_date'])}", f, "primary PS")
need(f1(ps["deepseek"]["primary"]["PS"]) + "pp", "09_limitations_repro.tex", "deepseek PS in sec 9")
assert fl["reading"] == "INCONCLUSIVE" and ps["pro"]["primary"]["reading"].startswith("BOUNDED") \
    and ps["deepseek"]["primary"]["reading"] == "DETECTED"

hi = json.loads((R / "rv1_hier.json").read_text())
for m in ("flash", "pro", "deepseek"):
    for e, v in hi[m].items():
        if "est" not in v:
            continue
        for k in ("date", "rep_x_date", "episode", "rep_x_episode"):
            need(ci(v[k]), "A5_appendix_robustness.tex", f"hier {m}/{e}/{k}")
need(ci(hi["flash"]["E2"]["rep_x_episode"]), "04_exp1_channels.tex", "sec 4.2 E2 rep x episode")
need(ci(hi["flash"]["E1"]["rep_x_episode"]), "04_exp1_channels.tex", "sec 4.2 E1 rep x episode")
need(ci(hi["flash"]["E3"]["rep_x_episode"]), "04_exp1_channels.tex", "sec 4.2 E3 rep x episode")

an = json.loads((R / "rv1_anachronism.json").read_text())["summary"]
fl_hits = sum(an["flash"][a]["responses_with_hit"] for a in "RDM")
fl_n = sum(an["flash"][a]["responses"] for a in "RDM")
if fl_hits != 0:
    fails.append("anachronism: flash has hits")
for f in ("00_abstract.tex", "01_intro.tex", "09_limitations_repro.tex"):
    need(f"0/{fl_n:,}", f, "flash anachronism n")
need(f"{an['pro']['D']['responses_with_hit']}/{an['pro']['D']['responses']}", "09_limitations_repro.tex", "pro D hits")
need(f"{an['pro']['M']['responses_with_hit']}/{an['pro']['M']['responses']}", "A5_appendix_robustness.tex", "pro M hits")
ds_n = sum(an["deepseek"][a]["responses"] for a in "RDM")
need(f"none in {ds_n:,}", "A5_appendix_robustness.tex", "deepseek n")

# whole-panel t values cited in E.14
wp = {l.split("|")[1].strip(): float(l.split("|")[4]) for l in (H / "outputs/bench/WHOLEPANEL_G.md").read_text().splitlines()
      if l.startswith("| ") and not l.startswith("| row") and l.split("|")[4].strip().lstrip("+-").replace(".", "").isdigit()}
for k, s in (("gpt-5.4-mini", "t=1.56"), ("qwen3.6-27b-fp8", "(0.63)"), ("qwen3.6-35b-a3b-fp8", "(0.69)")):
    if s.strip("()t=") != "%.2f" % wp[k]:
        fails.append(f"wholepanel {k}: printed {s}, file {wp[k]}")
    need(s.replace("t=", "$t=") if s.startswith("t=") else s, "A5_appendix_robustness.tex", f"wholepanel {k}")
conf = ["gemini-2.5-flash", "gemini-2.5-pro", "deepseek-v4-flash", "kimi-k2.6", "claude-sonnet-5", "claude-haiku-4-5", "gpt-5.5"]
if not all(wp[k] >= 1.96 for k in conf) or min(wp[k] for k in conf) != 2.61 or max(wp[k] for k in conf) != 6.45:
    fails.append("wholepanel: confirmed-row set or t range (2.61-6.45) does not match")
if not all(wp[k] >= 1.96 for k in ("gpt-5.5", "claude-sonnet-5", "kimi-k2.6")):
    fails.append("wholepanel: 2026-generation confirmed trio")

print("\n".join(fails) if fails else "OK: every RV-1 number in paper 1 matches its generated source; RV-1 freeze hashes intact")
sys.exit(1 if fails else 0)
