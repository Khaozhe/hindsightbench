#!/usr/bin/env python3
"""Check every downloaded weight shard against the sha256 the HF API lists for it (lfs.sha256 in the
.hf_api.json the ladder driver saved). The driver itself checks byte sizes only; this closes that gap
(added 2026-09-24 after two concurrent aria2 processes wrote the same shard of the addendum-J AWQ weights).

    python scripts/verify_weights_sha.py <weights dir>      # exit 1 on any mismatch or missing shard
"""
import hashlib, json, sys
from pathlib import Path

d = Path(sys.argv[1]); api = json.loads((d / ".hf_api.json").read_text())
bad = 0
for s in api["siblings"]:
    f = s["rfilename"]
    if not f.endswith(".safetensors"):
        continue
    want = (s.get("lfs") or {}).get("sha256")
    p = d / f
    if not p.exists():
        print("MISSING", f); bad += 1; continue
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 24), b""):
            h.update(b)
    ok = want is not None and h.hexdigest() == want
    bad += not ok
    print("OK" if ok else "MISMATCH", f, h.hexdigest()[:12], (want or "no-lfs-sha")[:12])
print("SHA_VERIFY_PASS" if bad == 0 else f"SHA_VERIFY_FAIL {bad}")
sys.exit(1 if bad else 0)
