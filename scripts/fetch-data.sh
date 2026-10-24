#!/usr/bin/env bash
set -euo pipefail
BASE="https://copper0722.github.io/gsat-vocabulary-map/data"
mkdir -p data
curl -fL "$BASE/vocabulary.json" -o data/vocabulary.json
curl -fL "$BASE/summary.json" -o data/summary.json
curl -fL "$BASE/gsat-vocabulary-frequency.csv" -o data/gsat-vocabulary-frequency.csv
echo "Data mirrored into ./data"
