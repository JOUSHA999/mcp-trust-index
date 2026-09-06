# MCP Trust Index

**Can you actually verify the MCP servers you install?**

A public-metadata audit of the entire official MCP registry. No permission needed, no
exploitation, no runtime testing — just facts that anyone can reproduce.

## Headline numbers (measured 2026-09-06, whole registry)

| | |
|---|---|
| Registry entries pulled | 93,296 |
| Unique MCP servers | **27,509** |
| Declare no repository and no package | **5,927 (21.5%)** |
| Declared GitHub repo links that 404 | **15.1%** (95% CI 13.2–17.2%) → ~2,750–3,583 servers |
| Version desync (registry ≠ npm) | **31.5%** (95% CI 28.4–34.8%) |
| Version desync (registry ≠ PyPI) | **25.4%** (95% CI 21.7–29.4%) |
| Servers exposing a remote endpoint | 15,550 (56.5%) · 0 over plain HTTP |

**Namespace nuance:** GitHub-verified `io.github.*` servers declare source 92.3% of the time;
unverified namespaces only 49.2%. The "no source" problem is concentrated in unverified namespaces.

## What this is NOT

- **Not a vulnerability scanner.** Nothing is executed, connected to, or tested against anyone's system.
- **Not an accusation.** A low grade means *"nobody outside the publisher can check this"* — not that it is unsafe.
- **Not hype.** Two of our own signals were downgraded after reading the data:
  - description drift between releases (~7%) turned out to be **benign copy edits**, published as monitoring only;
  - "registry description ≠ npm description" fires on **83.8%** of packages — pure noise, scored at **0 penalty**.

## Run it

```bash
bash run_all.sh        # quick: 1,000 entries -> sample pipeline
bash run_daily.sh      # full registry + CI samples + leaderboard (what CI runs)

python3 scripts/10_report.py io.github.someone/some-mcp   # per-server report -> reports/
python3 scripts/10_report.py --top 20                     # 20 worst in current sample
```

Requires `python3` (stdlib only) and `gh` authenticated for GitHub lookups.

## Layout

```
scripts/
  01_collect_registry.py   paginate official registry  (entry per VERSION — see 02b)
  02b_dedupe.py            collapse to unique servers   <-- critical
  02_enrich_packages.py    npm + PyPI metadata
  03_github.py             public repo status via gh
  04_score.py              rubric -> data/index.json
  05_site.py               static leaderboard
  06_drift.py              snapshot diff -> drift events
  07_registry_stats.py     registry-wide stats, zero API calls
  08_sample_deep.py        seeded random sample + 95% CI (GitHub, npm)
  09_pypi_sample.py        seeded random sample + 95% CI (PyPI)
  10_report.py             per-server printable Trust Report
  scoring.py               single source of truth for the rubric
data/  site/  reports/  snapshots/
rubric.md                  full published rubric
```

## Ethics

Public artifacts only · maintainer dispute and re-scan path · no exploit PoC ·
point-in-time scores, never a guarantee.

## Cost

$0. Official registry, npm and PyPI are free; `gh` gives 5,000 req/hr authenticated;
GitHub Actions + Pages are free at this volume (~600 min/mo of 2,000).
