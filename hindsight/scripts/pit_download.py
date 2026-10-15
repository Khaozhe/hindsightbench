#!/usr/bin/env python
"""Download point-in-time model ladders (Kelly et al. PIT-4B, DatedGPT) at pinned commits.

Runs on the cluster login node (the compute node has no internet); weights land on
/data next to the other hindsight models, so nothing is relayed through the Mac.

One sequential loop, one aria2c per file (two aria2 processes writing the same shard
corrupted AWQ weights once, see BM2c_note_J_serving.md). Every file is checked against
the sha256 the Hub API lists (LFS files) or its byte size (small git files), and a
per-repo manifest records repo, commit and file hashes. Re-running skips verified repos.

Usage: python pit_download.py [--mirror https://hf-mirror.com] [--dest DIR] [--only REGEX]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

YEARS_FIRST = ["2019", "2020", "2021", "2022", "2023", "2024"]
YEARS_REST = ["2013", "2014", "2015", "2016", "2017", "2018"]
PIT_TAG = {"2015": "201511"}  # PIT's 2015 checkpoint is November, every other one December


def pit(kind: str, y: str) -> str:
    return f"Diamegs/PIT-4B{kind}-{PIT_TAG.get(y, y + '12')}"


def queue() -> list[str]:
    q = []
    for years in (YEARS_FIRST, YEARS_REST):
        q += [f"datedgpt/datedgpt-{y}-instruct" for y in years]
        q += [pit("-FT", y) for y in years]
        q += [f"datedgpt/datedgpt-{y}-base" for y in years]
        q += [pit("", y) for y in years]
    return q


def log(msg: str) -> None:
    print(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg, flush=True)


def api(mirror: str, repo: str) -> dict:
    for attempt in range(5):
        try:
            # hf-mirror answers 403 to Python's default User-Agent
            req = urllib.request.Request(f"{mirror}/api/models/{repo}?blobs=true",
                                         headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            log(f"api retry {attempt + 1} {repo}: {e}")
            time.sleep(20)
    raise RuntimeError(f"api failed for {repo}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(mirror: str, repo: str, rev: str, name: str, out: Path, size: int, want: str | None) -> bool:
    def ok() -> bool:
        if not out.exists() or out.stat().st_size != size:
            return False
        return want is None or sha256(out) == want

    if ok():
        return True
    out.parent.mkdir(parents=True, exist_ok=True)
    url = f"{mirror}/{repo}/resolve/{rev}/{name}"
    for attempt in range(4):
        subprocess.run(
            ["aria2c", "-x8", "-s8", "-c", "--file-allocation=none", "--console-log-level=warn",
             "--summary-interval=0", "-d", str(out.parent), "-o", out.name, url],
            check=False,
        )
        if ok():
            return True
        log(f"verify failed {repo}/{name} attempt {attempt + 1}; deleting and retrying")
        out.unlink(missing_ok=True)
        Path(str(out) + ".aria2").unlink(missing_ok=True)
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", default="https://hf-mirror.com")
    ap.add_argument("--dest", default=str(Path.home() / "hindsight_models/pit"))
    ap.add_argument("--only", default=None, help="regex on repo id")
    a = ap.parse_args()
    dest = Path(a.dest)
    failed = []
    for repo in queue():
        if a.only and not re.search(a.only, repo):
            continue
        rdir = dest / repo.replace("/", "__")
        manifest = rdir / "download_manifest.json"
        if manifest.exists():
            log(f"SKIP verified {repo}")
            continue
        info = api(a.mirror, repo)
        rev = info["sha"]
        files = []
        good = True
        for s in info.get("siblings", []):
            name, size = s["rfilename"], s.get("size") or 0
            want = (s.get("lfs") or {}).get("sha256")
            if not fetch(a.mirror, repo, rev, name, rdir / name, size, want):
                good = False
                break
            files.append({"file": name, "size": size, "sha256": want or sha256(rdir / name)})
        if good:
            manifest.write_text(json.dumps({"repo": repo, "commit": rev, "files": files,
                                            "downloaded": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1))
            log(f"REPO_OK {repo} @ {rev[:8]} ({sum(f['size'] for f in files) / 1e9:.1f} GB)")
        else:
            failed.append(repo)
            log(f"REPO_FAIL {repo}")
    log(f"PIT_DOWNLOAD_END failed={failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
