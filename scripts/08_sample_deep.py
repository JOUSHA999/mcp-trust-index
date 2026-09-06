#!/usr/bin/env python3
"""
08_sample_deep.py — Random stratified sample -> deep signals that need external APIs.

GitHub rate limit is 5,000/hr, so we cannot check all 20,867 declared repos.
We take a seeded random sample and extrapolate with a 95% confidence interval.

Two samples:
  A) servers declaring a GitHub repo  -> does the repo actually resolve?
  B) servers declaring an npm package -> version desync + description drift (rug-pull shape)

Usage: python3 08_sample_deep.py [n_repos] [n_pkgs]
"""
import json, os, re, sys, time, math, random, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
DEDUP = os.path.join(ROOT, "data", "servers_dedup.json")
OUT = os.path.join(ROOT, "data", "sample_deep.json")
PAT = re.compile(r"github\.com[/:]([\w\-.]+)/([\w\-.]+?)(?:\.git)?/?$", re.I)
UA = {"User-Agent": "mcp-trust-index/0.1 (research)"}


def ci(p, n):
    if n == 0:
        return (0, 0)
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0, c - h), 1), round(100 * min(1, c + h), 1))


def gh(full):
    try:
        r = subprocess.run(["gh", "api", f"repos/{full}"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        d = json.loads(r.stdout)
        return {"stars": d.get("stargazers_count", 0), "archived": d.get("archived", False),
                "license": (d.get("license") or {}).get("spdx_id"),
                "pushed_at": d.get("pushed_at"), "fork": d.get("fork", False)}
    except Exception:
        return None


def npm(ident):
    try:
        req = urllib.request.Request("https://registry.npmjs.org/" + ident.replace("/", "%2F"), headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode())
    except Exception:
        return None
    v = d.get("versions", {})
    if not v:
        return None
    keys = list(v.keys())
    cur = d.get("dist-tags", {}).get("latest", keys[-1])
    if cur not in keys:
        return None
    i = keys.index(cur)
    prev = v.get(keys[i - 1], {}) if i > 0 else {}
    c = v.get(cur, {})
    return {"current": cur, "prev": keys[i - 1] if i > 0 else None,
            "n_versions": len(keys),
            "cur_desc": (c.get("description") or "").strip(),
            "prev_desc": (prev.get("description") or "").strip(),
            "deprecated": bool(c.get("deprecated"))}


def main():
    n_repo = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    n_pkg = int(sys.argv[2]) if len(sys.argv) > 2 else 800
    D = json.load(open(DEDUP))
    S = D["servers"]
    rnd = random.Random(20260906)

    # ---- sample A: github repos ----
    gh_cands = []
    for e in S:
        s = e["server"]
        r = s.get("repository")
        u = r.get("url") if isinstance(r, dict) else r
        if not u:
            continue
        m = PAT.search(u.strip())
        if m:
            gh_cands.append((s.get("name"), f"{m.group(1)}/{m.group(2)}"))
    sample_a = rnd.sample(gh_cands, min(n_repo, len(gh_cands)))
    print(f"[A] github: {len(gh_cands)} declared repos -> sampling {len(sample_a)}")
    with ThreadPoolExecutor(max_workers=10) as ex:
        res_a = list(ex.map(lambda t: (t[0], t[1], gh(t[1])), sample_a))

    dead = [r for r in res_a if r[2] is None]
    archived = [r for r in res_a if r[2] and r[2]["archived"]]
    nolicense = [r for r in res_a if r[2] and not r[2]["license"]]
    stale = []
    for _, _, g in res_a:
        if g and g.get("pushed_at"):
            try:
                t = time.mktime(time.strptime(g["pushed_at"], "%Y-%m-%dT%H:%M:%SZ"))
                if (time.time() - t) / 86400 > 365:
                    stale.append(g)
            except Exception:
                pass
    na = len(res_a)
    p_dead = len(dead) / na
    lo, hi = ci(p_dead, na)

    # ---- sample B: npm packages ----
    npm_cands = []
    for e in S:
        s = e["server"]
        for p in (s.get("packages") or []):
            if p.get("registryType") == "npm" and p.get("identifier"):
                npm_cands.append((s.get("name"), p["identifier"], p.get("version"), s.get("description", "")))
    sample_b = rnd.sample(npm_cands, min(n_pkg, len(npm_cands)))
    print(f"[B] npm: {len(npm_cands)} declared npm packages -> sampling {len(sample_b)}")
    with ThreadPoolExecutor(max_workers=12) as ex:
        res_b = list(ex.map(lambda t: (t[0], t[1], t[2], t[3], npm(t[1])), sample_b))

    ok_b = [r for r in res_b if r[4]]
    desync = [r for r in ok_b if r[2] and r[4]["current"] and r[2] != r[4]["current"]]
    drift = [r for r in ok_b if r[4]["prev_desc"] and r[4]["cur_desc"] and r[4]["prev_desc"] != r[4]["cur_desc"]]
    desc_mismatch = [r for r in ok_b if r[3].strip().lower()[:60] and r[4]["cur_desc"].strip().lower()[:60]
                     and r[3].strip().lower()[:60] != r[4]["cur_desc"].strip().lower()[:60]]
    missing_pkg = [r for r in res_b if not r[4]]
    nb = len(res_b)
    p_desync = len(desync) / nb
    lo2, hi2 = ci(p_desync, nb)

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "universe_declared_github_repos": len(gh_cands),
        "universe_declared_npm_packages": len(npm_cands),
        "github_sample": {
            "n": na, "dead": len(dead), "dead_pct": round(100 * p_dead, 1), "ci95": [lo, hi],
            "archived": len(archived), "no_license": len(nolicense), "stale_365d": len(stale),
            "extrapolated_dead": [round(len(gh_cands) * lo / 100), round(len(gh_cands) * hi / 100)],
        },
        "npm_sample": {
            "n": nb, "resolved": len(ok_b), "unresolved": len(missing_pkg),
            "version_desync": len(desync), "desync_pct": round(100 * p_desync, 1), "ci95": [lo2, hi2],
            "description_drift": len(drift), "drift_pct": round(100 * len(drift) / nb, 1),
            "desc_mismatch_vs_registry": len(desc_mismatch),
            "mismatch_pct": round(100 * len(desc_mismatch) / nb, 1),
            "extrapolated_desync": [round(len(npm_cands) * lo2 / 100), round(len(npm_cands) * hi2 / 100)],
        },
        "examples_dead_repo": [r[1] for r in dead[:15]],
        "examples_drift": [{"server": r[0], "pkg": r[1], "prev": r[4]["prev_desc"][:90],
                            "cur": r[4]["cur_desc"][:90]} for r in drift[:10]],
    }
    json.dump(out, open(OUT, "w"), indent=1)

    print("\n=== RESULTS ===")
    print(f"[A] dead repo links : {len(dead)}/{na} = {100*p_dead:.1f}%  (95% CI {lo}-{hi}%)")
    print(f"    -> extrapolated over {len(gh_cands)} declared repos: "
          f"{out['github_sample']['extrapolated_dead'][0]:,}-{out['github_sample']['extrapolated_dead'][1]:,} dead")
    print(f"    archived {len(archived)} · no-license {len(nolicense)} · stale>365d {len(stale)}")
    print(f"[B] version desync  : {len(desync)}/{nb} = {100*p_desync:.1f}%  (95% CI {lo2}-{hi2}%)")
    print(f"    description drift between releases: {len(drift)} ({out['npm_sample']['drift_pct']}%)")
    print(f"    registry-vs-npm description mismatch: {len(desc_mismatch)} ({out['npm_sample']['mismatch_pct']}%)")
    print(f"    npm package unresolved: {len(missing_pkg)}")


if __name__ == "__main__":
    main()
