#!/bin/bash
# MCP Trust Index — daily full run. Designed for GitHub Actions (free tier).
# Cost: $0. Needs GH_PAT (public-repo read) for >1,000 GitHub lookups/hr.
set -e
cd "$(dirname "$0")"
PY="${PY:-python3}"
REPO_N="${REPO_N:-1200}"   # GitHub repo-link sample  (rate: 5,000/hr with PAT)
NPM_N="${NPM_N:-800}"      # npm drift sample
PYPI_N="${PYPI_N:-500}"    # PyPI drift sample
LB_N="${LB_N:-600}"        # leaderboard random sample

echo "=== A. full registry ==="
$PY scripts/01_collect_registry.py 100000        # ~20 min, 933 API calls
$PY scripts/02b_dedupe.py                        # entries -> unique servers
cp data/servers_dedup.json data/servers_dedup_full.json
$PY scripts/07_registry_stats.py                 # registry-wide, no API calls

echo "=== B. deep random samples (95% CI) ==="
$PY scripts/08_sample_deep.py "$REPO_N" "$NPM_N"
$PY scripts/09_pypi_sample.py "$PYPI_N"

echo "=== C. leaderboard on unbiased random sample ==="
$PY - <<PYEOF
import json, random
D = json.load(open('data/servers_dedup_full.json'))
D['servers'] = random.Random(20260906).sample(D['servers'], min($LB_N, len(D['servers'])))
json.dump(D, open('data/servers_dedup.json', 'w'), indent=1)
print('leaderboard sample:', len(D['servers']))
PYEOF
$PY scripts/02_enrich_packages.py
$PY scripts/03_github.py
if [ -f data/index.json ]; then
  mkdir -p snapshots
  cp data/index.json "snapshots/index-$(date +%Y-%m-%dT%H%M).json"
  # keep only the 7 most recent snapshots — drift needs a baseline, git does not need history
  ls -1t snapshots/index-*.json | tail -n +8 | xargs -r rm -f
fi
$PY scripts/04_score.py
$PY scripts/06_drift.py || true

echo "=== D. render ==="
$PY scripts/05_site.py
echo "=== done ==="
