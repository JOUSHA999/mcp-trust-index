#!/usr/bin/env python3
"""
03_github.py — Public GitHub repo signals for each server that declares a repository.

Uses `gh api` (already authenticated -> 5,000 req/hr, $0).
Only PUBLIC metadata. No cloning, no code execution.

Signals:
  - archived / disabled
  - license present or not
  - stars
  - last push age  (stale = unmaintained)
  - default branch, topics
Output: data/github.json
"""
import json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
IN = os.path.join(HERE, "..", "data", "enriched.json")
OUT = os.path.join(HERE, "..", "data", "github.json")

PAT = re.compile(r"github\.com[/:]([\w\-.]+)/([\w\-.]+?)(?:\.git)?/?$", re.I)


def parse_repo(url):
    if not url:
        return None
    m = PAT.search(url.strip())
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"


def gh(path):
    try:
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def look(s):
    full = parse_repo(s.get("repository"))
    if not full:
        return {"name": s.get("name"), "repo": None}
    d = gh(f"repos/{full}")
    if not d or "full_name" not in d:
        return {"name": s.get("name"), "repo": full, "error": "not_found_or_private"}
    pushed = d.get("pushed_at")
    age = None
    if pushed:
        try:
            t = time.mktime(time.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ"))
            age = int((time.time() - t) / 86400)
        except Exception:
            pass
    return {
        "name": s.get("name"),
        "repo": full,
        "archived": d.get("archived", False),
        "disabled": d.get("disabled", False),
        "stars": d.get("stargazers_count", 0),
        "license": (d.get("license") or {}).get("spdx_id"),
        "pushed_at": pushed,
        "push_age_days": age,
        "open_issues": d.get("open_issues_count", 0),
        "fork": d.get("fork", False),
        "created_at": d.get("created_at"),
    }


def main():
    data = json.load(open(IN))
    servers = data["servers"]
    targets = [s for s in servers if s.get("repository")]
    print(f"github lookups: {len(targets)} / {len(servers)}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(look, targets))
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "count": len(res), "repos": res}, open(OUT, "w"), indent=1)
    ok = sum(1 for r in res if r.get("stars") is not None)
    print(f"OK -> {os.path.abspath(OUT)} ({ok} resolved)")


if __name__ == "__main__":
    main()
