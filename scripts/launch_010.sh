#!/usr/bin/env bash
# Exp 010 league launcher for the homelab HP (shared with GitHub Actions runners).
# Usage: bash scripts/launch_010.sh <commit> [league-name] [n-per-pairing] [workers]
#   e.g. bash scripts/launch_010.sh 1a2b3c4 league 10000 3
# Detached tmux session truco-010-<name>, nice 19, one thread per worker. Resumable: re-running
# the same command skips finished pairings. Log: logs/010/<name>.log.
# The HP venv (CPU torch, installed outside the lock) is built by hand; this script does no sync.
set -euo pipefail
commit=$1; name=${2:-league}; n=${3:-10000}; workers=${4:-3}
cd "$(dirname "$0")/.."
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
git checkout -q "$commit"
mkdir -p logs/010
session="truco-010-$name"
tmux new-session -d -s "$session" \
  "cd $PWD && echo \"start \$(date -Is) commit \$(git rev-parse --short HEAD) n=$n workers=$workers\" >> logs/010/$name.log && \
   OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 .venv/bin/python -m scripts.league_010 run --name $name --n $n --workers $workers >> logs/010/$name.log 2>&1; \
   echo \"exit \$? \$(date -Is)\" >> logs/010/$name.log"
echo "started tmux session $session at $(git rev-parse --short HEAD); log: $PWD/logs/010/$name.log"
