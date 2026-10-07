#!/usr/bin/env bash
# Exp 011 launcher (laptop): the 9 VonNeumann pairings on top of the 36 copied exp 010 files.
# Usage: bash scripts/launch_011.sh [workers]    (default 9)
# Refuses to start while a catan job is running (catan #46 measures latency: the two never overlap).
# Detached tmux session truco-011-league, nice 19, one thread per worker, log logs/011/league.log.
# Resumable: re-running skips finished pairings.
set -euo pipefail
workers=${1:-9}
cd "$(dirname "$0")/.."
if pgrep -f 'experiments.search_eval' >/dev/null; then
  echo "catan search_eval is running; not launching" >&2; exit 1
fi
PY=/media/guido/0DF7128F0DF7128F/truco-py-retrain-venv/bin/python
mkdir -p logs/011 results/011/league
# Exp 010 pairings, byte-identical (hashes in results/011/010_pairings.sha256).
for f in results/010/league/*__vs__*.json; do cp -n "$f" results/011/league/; done
(cd results/011/league && sha256sum -c --quiet ../010_pairings.sha256)
session="truco-011-league"
tmux new-session -d -s "$session" \
  "cd $PWD && echo \"start \$(date -Is) commit \$(git rev-parse --short HEAD) workers=$workers\" >> logs/011/league.log && \
   OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=$PWD nice -n 19 $PY -m scripts.league_010 run --name league --n 10000 --workers $workers --results-dir results/011 --manifest results/010/manifest.json --baselines threshold,random,vonneumann >> logs/011/league.log 2>&1; \
   echo \"exit \$? \$(date -Is)\" >> logs/011/league.log"
echo "started tmux session $session at $(git rev-parse --short HEAD); log: $PWD/logs/011/league.log"
