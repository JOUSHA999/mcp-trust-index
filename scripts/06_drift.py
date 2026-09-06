#!/usr/bin/env python3
"""
06_drift.py — Compare the current index against a previous snapshot.

This is the paid product's core: "we watch your server and tell you BEFORE your users notice."
Diffs: grade change, score change, new/removed flags, version change, description change.

Usage: python3 06_drift.py                # compare latest snapshot vs current index
       python3 06_drift.py snapshot.json  # compare an explicit snapshot
"""
import json, os, sys, glob, time

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
SNAP = os.path.join(ROOT, "snapshots")
IDX = os.path.join(ROOT, "data", "index.json")


def load(p):
    return {s["name"]: s for s in json.load(open(p))["servers"]}


def main():
    if not os.path.exists(IDX):
        sys.exit("no index.json — run 04_score.py first")
    cur = load(IDX)

    if len(sys.argv) > 1:
        prev_path = sys.argv[1]
    else:
        snaps = sorted(glob.glob(os.path.join(SNAP, "index-*.json")))
        if not snaps:
            os.makedirs(SNAP, exist_ok=True)
            json.dump(json.load(open(IDX)), open(os.path.join(SNAP, time.strftime("index-%Y-%m-%d.json")), "w"))
            print("no previous snapshot — baseline written")
            return
        prev_path = snaps[-1]

    prev = load(prev_path)
    print(f"baseline: {os.path.basename(prev_path)}  ({len(prev)} servers)")
    print(f"current : index.json ({len(cur)} servers)\n")

    events = []
    for name, c in cur.items():
        p = prev.get(name)
        if not p:
            events.append({"server": name, "type": "new_entry", "detail": f"grade {c['grade']}"})
            continue
        if c["grade"] != p["grade"]:
            events.append({"server": name, "type": "grade_change",
                           "detail": f"{p['grade']}({p['score']}) -> {c['grade']}({c['score']})",
                           "severity": "high"})
        pf = {f["id"] for f in p["flags"]}
        cf = {f["id"] for f in c["flags"]}
        new_f = cf - pf
        if new_f:
            ev = "high" if ("description_drift" in new_f or "repo_link_dead" in new_f) else "medium"
            events.append({"server": name, "type": "new_signal", "detail": ",".join(sorted(new_f)), "severity": ev})
        pv = (p["packages"] or [{}])[0].get("current")
        cv = (c["packages"] or [{}])[0].get("current")
        # catch both directions, including a package that stopped resolving (cv None)
        if pv != cv and (pv or cv):
            sev = "high" if cv is None else "medium"
            events.append({"server": name, "type": "version_change",
                           "detail": f"{pv or 'unresolved'} -> {cv or 'unresolved'}", "severity": sev})
        if (p.get("description") or "") != (c.get("description") or ""):
            events.append({"server": name, "type": "description_change", "severity": "high",
                           "detail": "registry description edited"})
    for name in prev:
        if name not in cur:
            events.append({"server": name, "type": "removed", "detail": "delisted from registry"})

    order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (order.get(e.get("severity", "low"), 2), e["type"]))
    json.dump({"compared_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "baseline": os.path.basename(prev_path), "events": events},
              open(os.path.join(ROOT, "data", "drift.json"), "w"), indent=1)

    print(f"{len(events)} drift events\n")
    for e in events[:40]:
        print(f"  [{e.get('severity','-')}] {e['type']:<20} {e['server']:<42} {e['detail']}")
    if len(events) > 40:
        print(f"  ... +{len(events)-40} more")


if __name__ == "__main__":
    main()
