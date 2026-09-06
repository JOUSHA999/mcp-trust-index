#!/usr/bin/env python3
"""
07_registry_stats.py — Registry-ONLY statistics over the WHOLE registry.

No external API calls, so this covers 100% of servers.
Answers: how many MCP servers can anyone actually verify?
"""
import json, os, time, collections, re

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
IN = os.path.join(ROOT, "data", "servers_dedup.json")
OUT = os.path.join(ROOT, "data", "registry_stats.json")


def main():
    d = json.load(open(IN))
    S = d["servers"]
    n = len(S)

    has_repo = has_pkg = has_remote = has_web = 0
    no_source = 0
    metadata_only = 0
    http_plain = 0
    remote_types = collections.Counter()
    pkg_types = collections.Counter()
    namespaces = collections.Counter()
    statuses = collections.Counter()
    versions_per = []

    for e in S:
        s = e["server"]
        meta = (e.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}) or {})
        statuses[meta.get("status") or "unknown"] += 1
        repo = s.get("repository")
        repo_url = repo.get("url") if isinstance(repo, dict) else repo
        pkgs = s.get("packages") or []
        remotes = s.get("remotes") or []
        if repo_url:
            has_repo += 1
        if pkgs:
            has_pkg += 1
        for p in pkgs:
            pkg_types[p.get("registryType")] += 1
        if remotes:
            has_remote += 1
        if s.get("websiteUrl"):
            has_web += 1
        if not repo_url and not pkgs:
            if remotes:
                no_source += 1
            else:
                metadata_only += 1
        for r in remotes:
            remote_types[r.get("type")] += 1
            if (r.get("url") or "").startswith("http://"):
                http_plain += 1
        nm = s.get("name") or ""
        ns = nm.split("/")[0].split(".")[0] if "/" in nm else nm.split(".")[0]
        namespaces[ns] += 1

    verifiable_declared = has_repo + has_pkg - len(
        [1 for e in S
         if (e["server"].get("repository") and (e["server"].get("packages") or []))])
    # cleaner
    both = 0
    for e in S:
        s = e["server"]
        repo = s.get("repository")
        ru = repo.get("url") if isinstance(repo, dict) else repo
        if ru and (s.get("packages") or []):
            both += 1
    declares_source = has_repo + has_pkg - both

    stats = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "unique_servers": n,
        "raw_entries": d.get("raw_entries"),
        "declares_repository": has_repo,
        "declares_package": has_pkg,
        "declares_any_source": declares_source,
        "declares_no_source": no_source,
        "metadata_only": metadata_only,
        "has_remote_endpoint": has_remote,
        "has_website": has_web,
        "plain_http_endpoints": http_plain,
        "remote_transport_types": dict(remote_types.most_common()),
        "package_registry_types": dict(pkg_types.most_common()),
        "top_namespaces": dict(namespaces.most_common(25)),
        "statuses": dict(statuses.most_common()),
        "pct": {
            "declares_any_source": round(100 * declares_source / n, 1),
            "declares_no_source": round(100 * no_source / n, 1),
            "metadata_only": round(100 * metadata_only / n, 1),
            "has_remote_endpoint": round(100 * has_remote / n, 1),
        },
    }
    json.dump(stats, open(OUT, "w"), indent=1)

    print(f"UNIQUE SERVERS: {n}  (from {d.get('raw_entries')} registry entries)")
    print(f"  declares repository : {has_repo:>6}  ({100*has_repo//n}%)")
    print(f"  declares package    : {has_pkg:>6}  ({100*has_pkg//n}%)")
    print(f"  declares ANY source : {declares_source:>6}  ({stats['pct']['declares_any_source']}%)")
    print(f"  declares NO source  : {no_source:>6}  ({stats['pct']['declares_no_source']}%)")
    print(f"  metadata only       : {metadata_only:>6}")
    print(f"  has remote endpoint : {has_remote:>6}  ({stats['pct']['has_remote_endpoint']}%)")
    print(f"  plain http endpoints: {http_plain:>6}")
    print(f"  transports: {stats['remote_transport_types']}")
    print(f"  pkg types : {stats['package_registry_types']}")
    print(f"  statuses  : {stats['statuses']}")
    print(f"  top namespaces: {list(stats['top_namespaces'].items())[:10]}")


if __name__ == "__main__":
    main()
