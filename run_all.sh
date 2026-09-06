#!/bin/bash
# MCP Trust Index — full pipeline. Zero cost: public APIs + GitHub Actions/Pages.
set -e
cd "$(dirname "$0")"
PY="${PY:-python3}"

echo "== 1/6 collect registry =="
$PY scripts/01_collect_registry.py "${1:-1000}"
echo "== 2/6 dedupe to unique servers =="
$PY scripts/02b_dedupe.py
echo "== 3/6 enrich npm + PyPI =="
$PY scripts/02_enrich_packages.py
echo "== 4/6 enrich GitHub =="
$PY scripts/03_github.py
echo "== 5/6 score =="
if [ -f data/index.json ]; then
  mkdir -p snapshots
  cp data/index.json "snapshots/index-$(date +%Y-%m-%dT%H%M).json"
fi
$PY scripts/04_score.py
echo "== 6/6 render site =="
$PY scripts/05_site.py
if [ -f "snapshots/index-$(date +%Y-%m-%d)*" ] || [ -d snapshots ]; then
  $PY scripts/06_drift.py || true
fi
echo "== done =="
