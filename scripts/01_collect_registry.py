#!/usr/bin/env python3
"""
01_collect_registry.py — Pull MCP server list from the Official MCP Registry API.

Source: https://registry.modelcontextprotocol.io  (public, no auth, no permission needed)
Output: data/servers_raw.json

Usage: python3 01_collect_registry.py [max_servers]
"""
import json, sys, time, urllib.request, urllib.parse, os

BASE = "https://registry.modelcontextprotocol.io/v0/servers"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "servers_raw.json")
UA = {"User-Agent": "mcp-security-index/0.1 (research; contact: local)"}


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                print(f"  ! fail {url[:80]} -> {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    servers, cursor, page = [], None, 0
    while len(servers) < target:
        url = f"{BASE}?limit=100"
        if cursor:
            url += "&" + urllib.parse.urlencode({"cursor": cursor})
        d = get(url)
        if not d or "servers" not in d:
            break
        batch = d["servers"]
        if not batch:
            break
        servers.extend(batch)
        cursor = d.get("metadata", {}).get("nextCursor")
        page += 1
        print(f"  page {page}: +{len(batch)} (total {len(servers)})")
        if not cursor:
            break
        time.sleep(0.4)

    servers = servers[:target]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "count": len(servers), "servers": servers}, f, indent=1)
    print(f"\nOK -> {os.path.abspath(OUT)}  ({len(servers)} servers)")


if __name__ == "__main__":
    main()
