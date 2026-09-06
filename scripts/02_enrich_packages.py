#!/usr/bin/env python3
"""
02_enrich_packages.py — For each registry server, pull npm / PyPI / GitHub PUBLIC metadata.

No permission needed. Everything here is public package-registry data.
Produces the signals the index scores on:
  - version drift   : registry version vs registry-latest published version
  - description drift (rug-pull signal) : current vs previous version description
  - package age     : first publish -> now
  - release burst   : many versions in a short window
  - maintainer/name mismatch, missing repository, http endpoint, etc.

Output: data/enriched.json
"""
import json, sys, os, time, re, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
IN = os.path.join(HERE, "..", "data", "servers_dedup.json")
OUT = os.path.join(HERE, "..", "data", "enriched.json")
UA = {"User-Agent": "mcp-security-index/0.1 (research)"}


def get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def npm_meta(ident):
    url = "https://registry.npmjs.org/" + ident.replace("/", "%2F")
    d = get(url)
    if not d or "versions" not in d:
        return None
    versions = d.get("versions", {})
    times = d.get("time", {})
    keys = list(versions.keys())
    if not keys:
        return None
    latest = versions.get(keys[-1], {})
    prev = versions.get(keys[-2], {}) if len(keys) > 1 else {}
    created = times.get("created") or times.get(keys[0])
    modified = times.get("modified") or times.get(keys[-1])
    # dist-tags latest is the real "current"
    dtags = d.get("dist-tags", {})
    cur_ver = dtags.get("latest", keys[-1])
    cur = versions.get(cur_ver, latest)
    # previous distinct version string before cur
    idx = keys.index(cur_ver) if cur_ver in keys else len(keys) - 1
    prev_ver = keys[idx - 1] if idx > 0 else None
    prev = versions.get(prev_ver, {}) if prev_ver else {}
    return {
        "registry": "npm",
        "identifier": ident,
        "current_version": cur_ver,
        "prev_version": prev_ver,
        "version_count": len(keys),
        "created": created,
        "modified": modified,
        "cur_desc": (cur.get("description") or "").strip(),
        "prev_desc": (prev.get("description") or "").strip(),
        "cur_repo": json.dumps(cur.get("repository") or ""),
        "maintainers": len(d.get("maintainers", []) or []),
        "deprecated": bool(cur.get("deprecated")),
        "unpacked": None,
    }


def pypi_meta(ident):
    d = get(f"https://pypi.org/pypi/{ident}/json")
    if not d:
        return None
    info = d.get("info", {})
    rel = d.get("releases", {}) or {}
    keys = [k for k in rel.keys() if rel.get(k)]
    if not keys:
        return None
    cur_ver = info.get("version", keys[-1])
    # release upload times
    times = {}
    for k, files in rel.items():
        if files:
            times[k] = files[0].get("upload_time")
    ordered = sorted(times.items(), key=lambda kv: kv[1] or "")
    created = ordered[0][1] if ordered else None
    prev_ver = None
    okeys = [k for k, _ in ordered]
    if cur_ver in okeys:
        i = okeys.index(cur_ver)
        if i > 0:
            prev_ver = okeys[i - 1]
    return {
        "registry": "pypi",
        "identifier": ident,
        "current_version": cur_ver,
        "prev_version": prev_ver,
        "version_count": len(keys),
        "created": created,
        "modified": ordered[-1][1] if ordered else None,
        "cur_desc": (info.get("summary") or "").strip(),
        "prev_desc": "",
        "cur_repo": (info.get("project_urls") or {}).get("Source", "") or (info.get("project_urls") or {}).get("Homepage", "") or "",
        "maintainers": 1,
        "deprecated": False,
    }


def enrich(entry):
    s = entry.get("server", {})
    name = s.get("name")
    out = {
        "name": name,
        "title": s.get("title"),
        "version": s.get("version"),
        "description": s.get("description", ""),
        "websiteUrl": s.get("websiteUrl"),
        "repository": s.get("repository", {}).get("url") if isinstance(s.get("repository"), dict) else (s.get("repository") or None),
        "remotes": s.get("remotes", []) or [],
        "packages": [],
        "status": (entry.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}) or {}).get("status"),
        "is_latest": (entry.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}) or {}).get("isLatest"),
        "published_at": (entry.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}) or {}).get("publishedAt"),
    }
    for p in s.get("packages", []) or []:
        ident, rt = p.get("identifier"), p.get("registryType")
        m = None
        if rt == "npm" and ident:
            m = npm_meta(ident)
        elif rt in ("pypi", "python") and ident:
            m = pypi_meta(ident)
        if m:
            m["declared_version"] = p.get("version")
            out["packages"].append(m)
        elif ident:
            out["packages"].append({"registry": rt, "identifier": ident, "unresolved": True,
                                    "declared_version": p.get("version"), "current_version": None,
                                    "cur_desc": "", "prev_desc": ""})
    return out


def main():
    raw = json.load(open(IN))
    servers = raw["servers"]
    print(f"enriching {len(servers)} servers ...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(enrich, servers))
    json.dump({"enriched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "count": len(res), "servers": res}, open(OUT, "w"), indent=1)
    npkg = sum(len(r["packages"]) for r in res)
    print(f"OK -> {os.path.abspath(OUT)}  ({len(res)} servers, {npkg} package records)")


if __name__ == "__main__":
    main()
