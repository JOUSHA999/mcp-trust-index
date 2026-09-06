#!/usr/bin/env python3
"""
04_score.py — Transparent, permission-free scoring of MCP servers.

WHAT THIS MEASURES:  verifiability + supply-chain stability.
WHAT IT DOES NOT MEASURE: whether the server is exploitable.
  -> No runtime testing, no exploitation, no access to anyone's system.
  -> Every input is public metadata from the official registry, npm, PyPI, GitHub.

Rubric is published in full at rubric.md so any maintainer can reproduce their own score.
"""
import json, os, time, html

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
ENR = os.path.join(ROOT, "data", "enriched.json")
GH = os.path.join(ROOT, "data", "github.json")

WEIGHTS = {
    "no_source_at_all":        (-40, "No repository and no package declared — source cannot be inspected by anyone"),
    "repo_link_dead":          (-35, "Declared GitHub repository returns 404 (deleted, renamed, or private)"),
    "repo_archived":           (-15, "Repository is archived — no longer maintained"),
    "repo_stale_365":          (-8,  "Repository not pushed to in over 365 days"),
    "no_license":              (-5,  "No open-source license declared"),
    "version_desync":          (-10, "Registry-declared version differs from the version published on npm/PyPI"),
    # v0.2: measured at 83.8% of npm packages -> no discriminative power. Kept as an informational
    # marker only, 0 penalty. Making it costly would punish normal publishing practice.
    "description_desync":      (0,   "Description in registry differs from description on npm/PyPI (informational only — very common)"),
    "description_drift":       (-20, "Package description changed between the last two releases (rug-pull signal)"),
    "remote_plain_http":       (-25, "Remote endpoint served over plain HTTP"),
    "unresolved_package":      (-12, "Declared npm/PyPI package does not resolve on the registry"),
    "no_endpoint_no_package":  (-10, "No endpoint, no package — entry is metadata only"),
    "repo_is_fork":            (-3,  "Repository is a fork"),
}

BANDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (20, "E"), (-1, "F")]


def grade(s):
    for lo, g in BANDS:
        if s >= lo:
            return g
    return "F"


def main():
    enr = json.load(open(ENR))
    gh_by = {}
    if os.path.exists(GH):
        for r in json.load(open(GH))["repos"]:
            gh_by[r["name"]] = r

    out = []
    for s in enr["servers"]:
        score, flags = 100, []
        gh = gh_by.get(s["name"])
        pkgs = s.get("packages") or []
        repo_url = s.get("repository")

        # --- verifiability ---
        if not repo_url and not pkgs:
            if not s.get("remotes"):
                flags.append("no_endpoint_no_package")
            else:
                flags.append("no_source_at_all")
        if repo_url and gh and gh.get("error"):
            flags.append("repo_link_dead")
        if gh and gh.get("archived"):
            flags.append("repo_archived")
        if gh and gh.get("repo") and not gh.get("license") and not gh.get("error"):
            flags.append("no_license")
        if gh and gh.get("fork"):
            flags.append("repo_is_fork")
        if gh and isinstance(gh.get("push_age_days"), int) and gh["push_age_days"] > 365:
            flags.append("repo_stale_365")

        # --- stability / drift ---
        for p in pkgs:
            dv, cv = p.get("declared_version"), p.get("current_version")
            if dv and cv and dv != cv:
                flags.append("version_desync")
                break
        for p in pkgs:
            rd = (s.get("description") or "").strip().lower()
            pd = (p.get("cur_desc") or "").strip().lower()
            if rd and pd and rd[:60] != pd[:60]:
                flags.append("description_desync")
                break
        for p in pkgs:
            if p.get("prev_desc") and p.get("cur_desc") and p["prev_desc"] != p["cur_desc"]:
                flags.append("description_drift")
                break

        for p in pkgs:
            if p.get("unresolved"):
                flags.append("unresolved_package")
                break

        # --- transport ---
        for r in s.get("remotes") or []:
            if (r.get("url") or "").startswith("http://"):
                flags.append("remote_plain_http")
                break

        uniq = []
        for f in flags:
            if f not in uniq:
                uniq.append(f)
        for f in uniq:
            score += WEIGHTS[f][0]
        score = max(0, min(100, score))

        verifiable = bool(pkgs) or bool(repo_url and gh and not gh.get("error"))

        out.append({
            "name": s["name"],
            "title": s.get("title"),
            "version": s.get("version"),
            "description": s.get("description", ""),
            "website": s.get("websiteUrl"),
            "repo": repo_url,
            "repo_live": (gh or {}).get("repo") if gh and not gh.get("error") else None,
            "stars": (gh or {}).get("stars"),
            "license": (gh or {}).get("license"),
            "push_age_days": (gh or {}).get("push_age_days"),
            "packages": [{"registry": p["registry"], "id": p["identifier"],
                          "declared": p.get("declared_version"), "current": p.get("current_version")} for p in pkgs],
            "remotes": [r.get("url") for r in (s.get("remotes") or [])],
            "score": score,
            "grade": grade(score),
            "verifiable": verifiable,
            "flags": [{"id": f, "penalty": WEIGHTS[f][0], "why": WEIGHTS[f][1]} for f in uniq],
        })

    out.sort(key=lambda x: (x["score"], x["name"]))
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n": len(out),
        "verifiable": sum(1 for o in out if o["verifiable"]),
        "grades": {g: sum(1 for o in out if o["grade"] == g) for g in "ABCDEF"},
        "flag_counts": {},
    }
    fc = {}
    for o in out:
        for f in o["flags"]:
            fc[f["id"]] = fc.get(f["id"], 0) + 1
    summary["flag_counts"] = dict(sorted(fc.items(), key=lambda kv: -kv[1]))

    json.dump({"summary": summary, "servers": out},
              open(os.path.join(ROOT, "data", "index.json"), "w"), indent=1)

    print(f"scored {len(out)} servers")
    print("verifiable:", summary["verifiable"], f"({100*summary['verifiable']//max(1,len(out))}%)")
    print("grades:", summary["grades"])
    print("flags:", summary["flag_counts"])
    return summary


if __name__ == "__main__":
    main()
