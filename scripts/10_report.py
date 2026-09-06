#!/usr/bin/env python3
"""
10_report.py — Generate a standalone "MCP Trust Report" for ANY server in the registry.

This is the sellable artifact: a one-page, printable (PDF-able) report a vendor can
be sent cold, and what the badge / monitoring subscription is sold against.

Usage: python3 10_report.py <server-name> [--out file.html]
       python3 10_report.py --top 10          # reports for the 10 worst in the current sample
"""
import json, os, sys, time, re, html, subprocess, urllib.request

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
from scoring import WEIGHTS, score_server  # noqa: E402

FULL = os.path.join(ROOT, "data", "servers_dedup_full.json")
IDX = os.path.join(ROOT, "data", "index.json")
OUTDIR = os.path.join(ROOT, "reports")
UA = {"User-Agent": "mcp-trust-index/0.1 (research)"}
PAT = re.compile(r"github\.com[/:]([\w\-.]+)/([\w\-.]+?)(?:\.git)?/?$", re.I)
GC = {"A": "#22c55e", "B": "#84cc16", "C": "#eab308", "D": "#f97316", "E": "#ef4444", "F": "#dc2626"}


def get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def npm_meta(ident):
    d = get("https://registry.npmjs.org/" + ident.replace("/", "%2F"))
    if not d or not d.get("versions"):
        return None
    v, keys = d["versions"], list(d["versions"].keys())
    cur = d.get("dist-tags", {}).get("latest", keys[-1])
    if cur not in keys:
        return None
    i = keys.index(cur)
    prev = v.get(keys[i - 1], {}) if i > 0 else {}
    c = v[cur]
    t = d.get("time", {})
    return {"registry": "npm", "identifier": ident, "current_version": cur,
            "prev_version": keys[i - 1] if i > 0 else None, "version_count": len(keys),
            "created": t.get("created"), "modified": t.get("modified"),
            "cur_desc": (c.get("description") or "").strip(),
            "prev_desc": (prev.get("description") or "").strip(),
            "maintainers": len(d.get("maintainers", []) or []), "unresolved": False}


def pypi_meta(ident):
    d = get(f"https://pypi.org/pypi/{ident}/json")
    if not d:
        return None
    info, rel = d.get("info", {}), d.get("releases", {}) or {}
    times = {k: f[0].get("upload_time") for k, f in rel.items() if f and f[0].get("upload_time")}
    if not times:
        return None
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
    return {"registry": "pypi", "identifier": ident, "current_version": cur, "prev_version": prev,
            "version_count": len(keys), "created": ordered[0][1], "modified": ordered[-1][1],
            "cur_desc": (info.get("summary") or "").strip(), "prev_desc": prev_sum,
            "maintainers": 1, "unresolved": False}


def gh_meta(url):
    m = PAT.search((url or "").strip())
    if not m:
        return None
    full = f"{m.group(1)}/{m.group(2)}"
    try:
        r = subprocess.run(["gh", "api", f"repos/{full}"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"repo": full, "error": "not_found_or_private"}
        d = json.loads(r.stdout)
    except Exception:
        return None
    pushed, age = d.get("pushed_at"), None
    if pushed:
        try:
            age = int((time.time() - time.mktime(time.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ"))) / 86400)
        except Exception:
            pass
    return {"repo": full, "archived": d.get("archived", False), "stars": d.get("stargazers_count", 0),
            "license": (d.get("license") or {}).get("spdx_id"), "pushed_at": pushed,
            "push_age_days": age, "open_issues": d.get("open_issues_count", 0),
            "fork": d.get("fork", False), "created_at": d.get("created_at")}


def build_rec(entry):
    s = entry["server"]
    meta = (entry.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}) or {})
    repo = s.get("repository")
    repo_url = repo.get("url") if isinstance(repo, dict) else repo
    rec = {"name": s.get("name"), "title": s.get("title"), "version": s.get("version"),
           "description": s.get("description", ""), "website": s.get("websiteUrl"),
           "repository": repo_url, "remotes": s.get("remotes") or [], "packages": []}
    for p in (s.get("packages") or []):
        ident, rt = p.get("identifier"), p.get("registryType")
        m = npm_meta(ident) if rt == "npm" else (pypi_meta(ident) if rt in ("pypi", "python") else None)
        if m:
            m["declared_version"] = p.get("version")
            rec["packages"].append(m)
        elif ident:
            rec["packages"].append({"registry": rt, "identifier": ident, "unresolved": True,
                                    "declared_version": p.get("version"), "current_version": None,
                                    "cur_desc": "", "prev_desc": ""})
    rec["_status"] = meta.get("status")
    return rec


def render(rec, gh, score, gr, flags, verifiable):
    rows = "".join(
        f'<tr class="{"noise" if WEIGHTS[f][0]==0 else ""}">'
        f'<td>{html.escape(WEIGHTS[f][1])}</td>'
        f'<td class="num">{WEIGHTS[f][0] if WEIGHTS[f][0] else "0"}</td></tr>' for f in flags
    ) or '<tr><td colspan="2" style="color:#4ade80">No signals detected — all checks clean.</td></tr>'

    pkg_rows = "".join(
        f'<tr><td>{html.escape(p.get("registry",""))}</td><td class="mono">{html.escape(p.get("identifier",""))}</td>'
        f'<td class="mono">{html.escape(str(p.get("declared_version") or "–"))}</td>'
        f'<td class="mono">{html.escape(str(p.get("current_version") or ("UNRESOLVED" if p.get("unresolved") else "–")))}</td>'
        f'<td class="num">{p.get("version_count","–")}</td></tr>' for p in rec["packages"]
    ) or '<tr><td colspan="5">No package declared</td></tr>'

    gh_html = "not declared"
    if rec["repository"] and gh:
        if gh.get("error"):
            gh_html = f'<b style="color:#f87171">DEAD LINK (404)</b> — <span class="mono">{html.escape(gh["repo"])}</span>'
        else:
            gh_html = (f'<a href="https://github.com/{html.escape(gh["repo"])}">{html.escape(gh["repo"])}</a> · '
                       f'{gh.get("stars",0)} stars · license {html.escape(str(gh.get("license")))} · '
                       f'last push {gh.get("push_age_days")}d ago'
                       + (" · <b>ARCHIVED</b>" if gh.get("archived") else ""))
    elif rec["repository"]:
        gh_html = html.escape(rec["repository"])

    remotes = "".join(f'<li class="mono">{html.escape(r.get("url",""))} ({html.escape(r.get("type",""))})</li>'
                      for r in rec["remotes"]) or "<li>none</li>"

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>MCP Trust Report — {html.escape(rec['name'])}</title>
<style>
body{{margin:0;background:#0b0f14;color:#e6edf3;font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
a{{color:#58a6ff}}
.wrap{{max-width:820px;margin:0 auto;padding:44px 24px}}
h1{{font-size:24px;margin:0 0 4px}}
.sub{{color:#8b949e;font-size:13px;margin-bottom:26px}}
.hero{{display:flex;gap:22px;align-items:center;background:#111823;border:1px solid #1f2937;border-radius:14px;padding:22px;margin-bottom:22px}}
.badge{{width:92px;height:92px;border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#08111c;font-weight:800}}
.badge .g{{font-size:40px;line-height:1}}
.badge .s{{font-size:13px;opacity:.8}}
.meta{{flex:1}}
.meta .n{{font-family:ui-monospace,monospace;font-size:13px;color:#8b949e}}
table{{width:100%;border-collapse:collapse;margin:8px 0 22px}}
th,td{{text-align:left;border-bottom:1px solid #1a212c;padding:9px 8px;font-size:14px}}
th{{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.06em}}
tr.noise td{{opacity:.6}}
.num{{text-align:right;font-family:ui-monospace,monospace}}
.mono{{font-family:ui-monospace,monospace;font-size:13px}}
h2{{font-size:16px;margin:26px 0 4px}}
.note{{color:#8b949e;font-size:12.5px;border-left:3px solid #30363d;padding-left:12px;margin:12px 0}}
footer{{margin-top:36px;color:#6e7681;font-size:11.5px;border-top:1px solid #1f2937;padding-top:14px}}
@media print{{body{{background:#fff;color:#000}} .hero,table th,table td{{border-color:#bbb}}}}
</style></head><body><div class="wrap">
<h1>MCP Trust Report</h1>
<div class="sub">Public-metadata verifiability audit · generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}</div>

<div class="hero">
<div class="badge" style="background:{GC[gr]}"><div class="g">{gr}</div><div class="s">{score}/100</div></div>
<div class="meta">
<div style="font-size:19px;font-weight:600">{html.escape(rec['title'] or rec['name'])}</div>
<div class="n">{html.escape(rec['name'])} · v{html.escape(str(rec['version']))}</div>
<div style="margin-top:8px;font-size:13px">Verifiable from public source:
<b style="color:{'#4ade80' if verifiable else '#f87171'}">{'YES' if verifiable else 'NO'}</b>
{'· status: ' + html.escape(str(rec.get('_status'))) if rec.get('_status') else ''}</div>
</div></div>

<h2>What was checked</h2>
<div class="note">Public metadata only: the official MCP Registry, npm, PyPI and public GitHub repo status.
<b>Nothing was executed, connected to, or tested against any system.</b>
This report states whether an outside party can verify this server — it does not claim the server is or is not secure.</div>

<h2>Signals</h2>
<table><thead><tr><th>Finding</th><th class="num">Penalty</th></tr></thead><tbody>{rows}</tbody></table>

<h2>Distribution</h2>
<table><thead><tr><th>Registry</th><th>Package</th><th>Declared v.</th><th>Published v.</th><th class="num">Versions</th></tr></thead>
<tbody>{pkg_rows}</tbody></table>

<h2>Source</h2>
<table><tbody>
<tr><td style="width:150px">Repository</td><td>{gh_html}</td></tr>
<tr><td>Website</td><td>{('<a href="'+html.escape(rec['website'])+'">'+html.escape(rec['website'])+'</a>') if rec['website'] else 'not declared'}</td></tr>
<tr><td>Remote endpoints</td><td><ul style="margin:0;padding-left:16px">{remotes}</ul></td></tr>
</tbody></table>

<h2>How to improve this score</h2>
<div class="note">Publish the source (add <span class="mono">repository</span> to your registry entry or ship a package),
keep the registry version in sync with npm/PyPI, add a licence, and keep the repository alive.
Then open an issue and we re-scan.</div>

<footer>Full rubric: rubric.md · Scores are point-in-time · Dispute and re-scan path: open an issue.
No exploitation, no runtime testing and no access to third-party systems were used to produce this report.</footer>
</div></body></html>"""


def make(name, outdir=OUTDIR):
    D = json.load(open(FULL))
    entry = next((e for e in D["servers"] if e["server"].get("name") == name), None)
    if not entry:
        return None, f"not found in registry: {name}"
    rec = build_rec(entry)
    gh = gh_meta(rec["repository"]) if rec["repository"] else None
    score, gr, flags = score_server(rec, gh)
    verifiable = bool(rec["packages"]) or bool(gh and not gh.get("error"))
    os.makedirs(outdir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    path = os.path.join(outdir, f"report-{safe}.html")
    open(path, "w").write(render(rec, gh, score, gr, flags, verifiable))
    return path, f"{gr} {score}/100 verifiable={verifiable} flags={flags}"


def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    if args[0] == "--top":
        k = int(args[1]) if len(args) > 1 else 10
        idx = json.load(open(IDX))
        for o in idx["servers"][:k]:
            p, msg = make(o["name"])
            print(f"{o['name'][:46]:<48} {msg} -> {p}")
        return
    p, msg = make(args[0])
    print(msg)
    print(p if p else "")


if __name__ == "__main__":
    main()
