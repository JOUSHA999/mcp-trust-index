#!/usr/bin/env python3
"""
09_pypi_sample.py — Same drift analysis as the npm sample, for PyPI packages.

npm was sampled in 08; PyPI was left out (3,607 declared packages). This closes the gap.
For each sampled package: resolve current version, fetch the PREVIOUS version's metadata,
and compare summaries -> description drift (rug-pull shape, though usually benign).

Usage: python3 09_pypi_sample.py [n]
"""
import json, os, sys, time, math, random, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
DEDUP = os.path.join(ROOT, "data", "servers_dedup_full.json")
OUT = os.path.join(ROOT, "data", "sample_pypi.json")
UA = {"User-Agent": "mcp-trust-index/0.1 (research)"}


def get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def ci(p, n):
    if n == 0:
        return (0, 0)
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0, c - h), 1), round(100 * min(1, c + h), 1))


def probe(ident):
    d = get(f"https://pypi.org/pypi/{ident}/json")
    if not d:
        return {"id": ident, "resolved": False}
    info = d.get("info", {})
    rel = d.get("releases", {}) or {}
    times = {}
    for k, files in rel.items():
        if files:
            up = files[0].get("upload_time")
            if up:
                times[k] = up
    if not times:
        return {"id": ident, "resolved": False}
    ordered = sorted(times.items(), key=lambda kv: kv[1])
    keys = [k for k, _ in ordered]
    cur = info.get("version") or keys[-1]
    idx = keys.index(cur) if cur in keys else len(keys) - 1
    prev = keys[idx - 1] if idx > 0 else None
    prev_sum = ""
    if prev:
        pv = get(f"https://pypi.org/pypi/{ident}/{prev}/json")
        if pv:
            prev_sum = (pv.get("info", {}).get("summary") or "").strip()
    cur_sum = (info.get("summary") or "").strip()
    return {"id": ident, "resolved": True, "current": cur, "prev": prev,
            "n_versions": len(keys), "cur_sum": cur_sum, "prev_sum": prev_sum,
            "created": ordered[0][1], "modified": ordered[-1][1]}


def main():
    n_target = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    D = json.load(open(DEDUP))
    S = D["servers"]
    rnd = random.Random(20260906)

    cands = []
    for e in S:
        s = e["server"]
        for p in (s.get("packages") or []):
            if p.get("registryType") in ("pypi", "python") and p.get("identifier"):
                cands.append((s.get("name"), p["identifier"], p.get("version")))
    sample = rnd.sample(cands, min(n_target, len(cands)))
    print(f"pypi: {len(cands)} declared -> sampling {len(sample)}")

    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(lambda t: (t[0], t[1], t[2], probe(t[1])), sample))

    ok = [r for r in res if r[3]["resolved"]]
    unresolved = len(res) - len(ok)
    desync = [r for r in ok if r[2] and r[3].get("current") and r[2] != r[3]["current"]]
    drift = [r for r in ok if r[3].get("prev_sum") and r[3].get("cur_sum")
             and r[3]["prev_sum"] != r[3]["cur_sum"]]
    n = len(ok)
    p_desync = len(desync) / max(1, n)
    lo, hi = ci(p_desync, n)

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "universe_declared_pypi": len(cands),
        "sample": {"n_sampled": len(res), "resolved": n, "unresolved": unresolved,
                   "version_desync": len(desync), "desync_pct": round(100 * p_desync, 1),
                   "ci95": [lo, hi],
                   "extrapolated_desync": [round(len(cands) * lo / 100), round(len(cands) * hi / 100)],
                   "description_drift": len(drift), "drift_pct": round(100 * len(drift) / max(1, n), 1)},
        "examples_drift": [{"server": r[0], "pkg": r[1], "prev": r[3]["prev_sum"][:90],
                            "cur": r[3]["cur_sum"][:90]} for r in drift[:10]],
    }
    json.dump(out, open(OUT, "w"), indent=1)

    print("\n=== PyPI RESULTS ===")
    print(f"resolved          : {n}/{len(res)}  (unresolved {unresolved})")
    print(f"version desync    : {len(desync)} = {100*p_desync:.1f}%  (95% CI {lo}-{hi}%)")
    print(f"  -> extrapolated : {out['sample']['extrapolated_desync'][0]:,}-{out['sample']['extrapolated_desync'][1]:,} of {len(cands):,}")
    print(f"description drift : {len(drift)} ({out['sample']['drift_pct']}%)")
    for e in out["examples_drift"][:5]:
        print(f"   * {e['pkg']}\n     PREV: {e['prev']}\n     CUR : {e['cur']}")


if __name__ == "__main__":
    main()
