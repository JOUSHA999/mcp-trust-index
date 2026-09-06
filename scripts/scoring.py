#!/usr/bin/env python3
"""scoring.py — single source of truth for the rubric. Imported by 04_score.py and 10_report.py."""

WEIGHTS = {
    "no_source_at_all":       (-40, "No repository and no package declared — source cannot be inspected by anyone"),
    "repo_link_dead":         (-35, "Declared GitHub repository returns 404 (deleted, renamed, or private)"),
    "repo_archived":          (-15, "Repository is archived — no longer maintained"),
    "repo_stale_365":         (-8,  "Repository not pushed to in over 365 days"),
    "no_license":             (-5,  "No open-source license declared"),
    "version_desync":         (-10, "Registry-declared version differs from the version published on npm/PyPI"),
    # v0.2 — measured at 83.8% of npm packages: no discriminative power. Informational only.
    "description_desync":     (0,   "Description in registry differs from description on npm/PyPI (informational)"),
    "description_drift":      (-20, "Package description changed between the last two releases (monitoring signal)"),
    "remote_plain_http":      (-25, "Remote endpoint served over plain HTTP"),
    "no_endpoint_no_package": (-10, "No endpoint, no package — entry is metadata only"),
    "repo_is_fork":           (-3,  "Repository is a fork"),
    "unresolved_package":     (-12, "Declared npm/PyPI package does not resolve on the registry"),
}

BANDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (20, "E"), (-1, "F")]


def grade(score):
    for lo, g in BANDS:
        if score >= lo:
            return g
    return "F"


def score_server(rec, gh=None):
    """rec: enriched server record. gh: github record or None. Returns (score, grade, [flag ids])."""
    flags = []
    pkgs = rec.get("packages") or []
    repo_url = rec.get("repository")

    if not repo_url and not pkgs:
        flags.append("no_endpoint_no_package" if not rec.get("remotes") else "no_source_at_all")
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

    for p in pkgs:
        if p.get("unresolved"):
            flags.append("unresolved_package")
            break
    for p in pkgs:
        dv, cv = p.get("declared_version"), p.get("current_version")
        if dv and cv and dv != cv:
            flags.append("version_desync")
            break
    for p in pkgs:
        rd = (rec.get("description") or "").strip().lower()
        pd = (p.get("cur_desc") or "").strip().lower()
        if rd and pd and rd[:60] != pd[:60]:
            flags.append("description_desync")
            break
    for p in pkgs:
        if p.get("prev_desc") and p.get("cur_desc") and p["prev_desc"] != p["cur_desc"]:
            flags.append("description_drift")
            break

    for r in rec.get("remotes") or []:
        if (r.get("url") or "").startswith("http://"):
            flags.append("remote_plain_http")
            break

    uniq = []
    for f in flags:
        if f not in uniq:
            uniq.append(f)
    score = max(0, min(100, 100 + sum(WEIGHTS[f][0] for f in uniq)))
    return score, grade(score), uniq
