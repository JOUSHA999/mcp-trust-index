#!/usr/bin/env python3
"""
02b_dedupe.py — The registry API returns ONE ENTRY PER VERSION, not per server.
This collapses to unique servers and keeps the latest version record.

Output: data/servers_dedup.json
"""
import json, os, time, collections

HERE = os.path.dirname(__file__)
IN = os.path.join(HERE, "..", "data", "servers_raw.json")
OUT = os.path.join(HERE, "..", "data", "servers_dedup.json")


def vkey(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def main():
    raw = json.load(open(IN))
    by = {}
    for e in raw["servers"]:
        s = e["server"]
        meta = (e.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}) or {})
        name = s.get("name")
        cur = by.get(name)
        rec = (s, meta, vkey(s.get("version")))
        if cur is None:
            by[name] = rec
        else:
            # prefer isLatest, else highest version, else newest updatedAt
            if meta.get("isLatest") and not cur[1].get("isLatest"):
                by[name] = rec
            elif meta.get("isLatest") == cur[1].get("isLatest"):
                if rec[2] > cur[2]:
                    by[name] = rec
                elif rec[2] == cur[2] and (meta.get("updatedAt") or "") > (cur[1].get("updatedAt") or ""):
                    by[name] = rec

    out = []
    for name, (s, meta, _) in by.items():
        out.append({"server": s, "_meta": {"io.modelcontextprotocol.registry/official": meta}})
    json.dump({"collected_at": raw.get("collected_at"),
               "raw_entries": len(raw["servers"]),
               "unique_servers": len(out),
               "servers": out}, open(OUT, "w"), indent=1)
    print(f"raw entries {len(raw['servers'])} -> unique servers {len(out)}")
    print(f"OK -> {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
