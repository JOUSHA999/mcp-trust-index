#!/usr/bin/env python3
"""05_site.py — Render the static index (GitHub Pages ready, no framework)."""
import json, os, html

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
SITE = os.path.join(ROOT, "site")
os.makedirs(SITE, exist_ok=True)

GC = {"A": "#22c55e", "B": "#84cc16", "C": "#eab308", "D": "#f97316", "E": "#ef4444", "F": "#dc2626"}
FL = {
    "no_source_at_all": "No source published",
    "repo_link_dead": "Dead repo link (404)",
    "repo_archived": "Archived",
    "repo_stale_365": "Stale >365d",
    "no_license": "No license",
    "version_desync": "Version desync",
    "description_desync": "Description differs (informational)",
    "description_drift": "Description changed between releases",
    "remote_plain_http": "Plain HTTP endpoint",
    "no_endpoint_no_package": "Metadata only",
    "repo_is_fork": "Fork",
    "unresolved_package": "Declared package does not resolve",
}
NOISE = {"description_desync"}


def load(p, default=None):
    if os.path.exists(p):
        return json.load(open(p))
    return default if default is not None else {}


def build():
    idx = load(os.path.join(ROOT, "data", "index.json"), {"summary": {}, "servers": []})
    stats = load(os.path.join(ROOT, "data", "registry_stats.json"))
    deep = load(os.path.join(ROOT, "data", "sample_deep.json"))
    pypi = load(os.path.join(ROOT, "data", "sample_pypi.json"), {}).get("sample", {})

    s, servers = idx.get("summary", {}), idx.get("servers", [])
    n = s.get("n", 0)
    ver = s.get("verifiable", 0)
    pct = round(100 * ver / max(1, n))

    rows = []
    for i, o in enumerate(servers, 1):
        g = o["grade"]
        chips = []
        for fl in o["flags"]:
            cls = "f n" if fl["id"] in NOISE else "f"
            pen = "" if fl["penalty"] == 0 else f" &minus;{abs(fl['penalty'])}"
            chips.append(f'<span class="{cls}">{html.escape(FL.get(fl["id"], fl["id"]))}{pen}</span>')
        chips = "".join(chips) or '<span class="f ok">no signals</span>'
        link = ""
        if o.get("repo_live"):
            link = f'<a href="https://github.com/{html.escape(o["repo_live"])}" target="_blank">repo</a>'
        elif o.get("repo"):
            link = '<span class="dead">repo 404</span>'
        if o.get("website"):
            link += f' · <a href="{html.escape(o["website"])}" target="_blank">site</a>'
        rows.append(f"""<tr>
<td class="rk">{i}</td>
<td class="nm"><div class="t">{html.escape(o.get('title') or o['name'])}</div>
<div class="sn">{html.escape(o['name'])}</div><div class="lk">{link}</div></td>
<td><span class="g" style="background:{GC[g]}">{g}</span></td>
<td class="sc">{o['score']}</td>
<td class="fl">{chips}</td>
<td class="vf">{'yes' if o['verifiable'] else '<b style="color:#f87171">no</b>'}</td>
</tr>""")

    grade_cards = "".join(
        f'<div class="card"><div class="v" style="color:{GC[g]}">{s.get("grades",{}).get(g,0)}</div>'
        f'<div class="l">Grade {g}</div></div>' for g in "ABCDEF")

    flag_rows = "".join(
        f'<tr><td>{html.escape(FL.get(k,k))}</td><td class="num">{v}</td>'
        f'<td class="num">{round(100*v/max(1,n))}%</td></tr>'
        for k, v in sorted(s.get("flag_counts", {}).items(), key=lambda kv: -kv[1]))

    U = stats.get("unique_servers", 0)
    NOS = stats.get("declares_no_source", 0)
    gh_s = deep.get("github_sample", {})
    np_s = deep.get("npm_sample", {})

    def f(x):
        return f"{x:,}"

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MCP Trust Index — can you verify the MCP servers you install?</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0b0f14;color:#e6edf3;font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
a{{color:#58a6ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.wrap{{max-width:1120px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:32px;margin:0 0 8px;letter-spacing:-.02em}}
.sub{{color:#8b949e;margin-bottom:28px;font-size:16px}}
.hero{{background:#111823;border:1px solid #1f2937;border-radius:14px;padding:24px;margin-bottom:24px}}
.big{{font-size:40px;font-weight:700;line-height:1.15}}
.big em{{color:#f87171;font-style:normal}}
.big span{{font-size:15px;color:#8b949e;font-weight:400;display:block;margin-top:8px}}
.grid3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:22px}}
.box{{background:#0e1420;border:1px solid #1f2937;border-radius:10px;padding:16px}}
.box .v{{font-size:28px;font-weight:700;color:#f87171}}
.box .v.g{{color:#e6edf3}}
.box .l{{color:#8b949e;font-size:12px;margin-top:4px}}
.box .d{{color:#6e7681;font-size:11px;margin-top:6px;line-height:1.4}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:12px;margin:22px 0 8px}}
.card{{background:#0e1420;border:1px solid #1f2937;border-radius:10px;padding:14px;text-align:center}}
.card .v{{font-size:26px;font-weight:700}}.card .l{{color:#8b949e;font-size:12px;margin-top:2px}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}
th{{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#8b949e;border-bottom:1px solid #1f2937;padding:10px 8px}}
td{{border-bottom:1px solid #151c26;padding:12px 8px;vertical-align:top}}
.rk{{color:#6e7681;width:38px}}
.nm .t{{font-weight:600}}.nm .sn{{font-size:12px;color:#6e7681;font-family:ui-monospace,monospace}}
.nm .lk{{font-size:12px;margin-top:3px}}.dead{{color:#f87171}}
.g{{display:inline-block;min-width:24px;text-align:center;color:#08111c;font-weight:800;border-radius:5px;padding:1px 7px;font-size:13px}}
.sc{{font-family:ui-monospace,monospace;color:#8b949e;width:48px}}
.f{{display:inline-block;background:#1b2430;border:1px solid #2a3543;color:#c9d1d9;font-size:11px;border-radius:20px;padding:2px 9px;margin:2px 4px 2px 0}}
.f.n{{opacity:.55}}
.f.ok{{background:#0f2a1a;border-color:#1c4a2e;color:#4ade80}}
.vf{{width:58px;font-size:13px}}
h2{{font-size:20px;margin:44px 0 6px}}
.note{{color:#8b949e;font-size:13px;border-left:3px solid #30363d;padding-left:12px;margin:14px 0}}
footer{{margin-top:50px;color:#6e7681;font-size:12px;border-top:1px solid #1f2937;padding-top:16px}}
.num{{text-align:right;font-family:ui-monospace,monospace}}
</style></head><body><div class="wrap">

<h1>MCP Trust Index</h1>
<div class="sub">Can you actually verify the MCP servers you install? A public-metadata audit of the
entire official MCP registry.</div>

<div class="hero">
<div class="big"><em>{f(NOS)}</em> MCP servers publish no source code at all
<span>Out of {f(U)} unique servers in the official MCP Registry · measured {stats.get('generated_at','')[:10]}</span></div>
<div class="grid3">
  <div class="box"><div class="v">{gh_s.get('dead_pct','–')}%</div><div class="l">of declared GitHub repo links are dead</div>
    <div class="d">Random sample of {f(gh_s.get('n',0))} · 95% CI {gh_s.get('ci95',['',''])[0]}–{gh_s.get('ci95',['',''])[1]}%
    → ~{f(gh_s.get('extrapolated_dead',[0,0])[0])}–{f(gh_s.get('extrapolated_dead',[0,0])[1])} dead links registry-wide</div></div>
  <div class="box"><div class="v">{np_s.get('desync_pct','–')}%</div><div class="l">version desync: registry ≠ npm</div>
    <div class="d">Random sample of {f(np_s.get('n',0))} npm packages ·
    95% CI {np_s.get('ci95',['',''])[0]}–{np_s.get('ci95',['',''])[1]}%<br>
    PyPI: {pypi.get('desync_pct','–')}% (95% CI {pypi.get('ci95',['',''])[0]}–{pypi.get('ci95',['',''])[1]}%, n={f(pypi.get('n_sampled',0))})</div></div>
  <div class="box"><div class="v g">{stats.get('pct',{}).get('has_remote_endpoint','–')}%</div><div class="l">expose a remote endpoint</div>
    <div class="d">{f(stats.get('has_remote_endpoint',0))} servers reachable over the network;
    0 serve plain HTTP</div></div>
</div>
</div>

<h2>What this measures</h2>
<div class="note">
<b>Verifiability and supply-chain stability — not exploitability.</b>
Every input is public metadata: the official MCP Registry, npm, PyPI, and public GitHub repo status.
Nothing here runs, connects to, or tests anyone's server. A low grade means
<i>"nobody outside the publisher can check what this thing does"</i> — never a claim that it is malicious.
</div>

<h2>Honest caveats — read before quoting us</h2>
<div class="note">
1. <b>Description drift is mostly benign.</b> {np_s.get('drift_pct','–')}% of sampled npm packages changed their
description between the last two releases. We read the examples: nearly all are marketing copy edits and
feature announcements, <b>not</b> rug-pulls. We publish it as a monitoring signal only.<br>
2. <b>"Description differs between registry and npm" is noise, not a signal.</b> It fires on
{np_s.get('mismatch_pct','–')}% of packages, so it carries no information — we score it at 0 penalty.<br>
3. <b>Namespaces matter.</b> GitHub-verified <code>io.github.*</code> servers declare source
{round(100-7.7,1)}% of the time; unverified namespaces only {round(100-50.8,1)}%. The "no source" problem is
concentrated in unverified namespaces.<br>
4. <b>Point-in-time.</b> Scores describe the moment of the scan.
</div>

<h2>Registry-wide coverage</h2>
<table>
<tr><td>Registry entries pulled</td><td class="num">{f(stats.get('raw_entries',0))}</td></tr>
<tr><td>Unique servers (after version dedupe)</td><td class="num">{f(U)}</td></tr>
<tr><td>Declare a repository</td><td class="num">{f(stats.get('declares_repository',0))}</td></tr>
<tr><td>Declare a package</td><td class="num">{f(stats.get('declares_package',0))}</td></tr>
<tr><td>Declare <b>no</b> source at all</td><td class="num">{f(NOS)} ({stats.get('pct',{}).get('declares_no_source','–')}%)</td></tr>
<tr><td>Still listed but deprecated</td><td class="num">{f(stats.get('statuses',{}).get('deprecated',0))}</td></tr>
</table>

<h2>Leaderboard — random sample of {n} servers</h2>
<div class="stats">{grade_cards}</div>
<div class="note">Seeded random sample (seed 20260906) of {n} from {f(U)} unique servers.
{ver} of {n} ({pct}%) are verifiable from public source.</div>

<h2>Signal frequency (sample)</h2>
<table><thead><tr><th>Signal</th><th class="num">Servers</th><th class="num">Share</th></tr></thead>
<tbody>{flag_rows}</tbody></table>

<h2>Leaderboard</h2>
<table><thead><tr><th>#</th><th>Server</th><th>Grade</th><th>Score</th><th>Signals</th><th>Verifiable</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>

<footer>
Every deduction is published and reproducible — see rubric.md. Scores are point-in-time.
Maintainer dispute and re-scan path: open an issue.
No exploitation, no runtime testing, and no access to third-party systems were used to produce this page.
</footer>
</div></body></html>"""
    open(os.path.join(SITE, "index.html"), "w").write(page)
    print("site ->", os.path.join(SITE, "index.html"))


if __name__ == "__main__":
    build()
