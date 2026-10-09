#!/usr/bin/env bash
# Experiment 013 (docs/experiments/013-*.md): fair vs Threshold and fair vs omniscient VonNeumann.
# n=2000 each, seat-rotated, r=20, seed base of log 009, in-memory cache, ONE worker, nice 19.
# Resumable (skips arms whose JSON exists). Meant for the HP inside tmux session truco-050:
#   tmux new -d -s truco-050 'bash scripts/run_013.sh'
# Stop: tmux send-keys -t truco-050 C-c   (the current arm restarts from zero on resume).
set -u
cd "$(dirname "$0")/.."

N=2000
SEED=20261002
PY=${PY:-.venv/bin/python}
mkdir -p results/013 logs/013

ARMS=(
  "fair_vs_thr|match_von_neumann_determinized_vs_threshold"
  "fair_vs_omni|match_von_neumann_determinized_vs_von_neumann_omniscient"
)

for job in "${ARMS[@]}"; do
  IFS='|' read -r name mode <<<"$job"
  out="results/013/$name.json"
  [ -f "$out" ] && { echo "skip $name (done)"; continue; }
  echo "$(date -Is) start $name"
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH="$PWD" \
    nice -n 19 "$PY" scripts/benchmark.py --mode "$mode" --n "$N" --seed "$SEED" --rollouts 20 \
    --out "$out" 2>&1 | tee -a "logs/013/$name.log"
  echo "$(date -Is) end   $name rc=${PIPESTATUS[0]}"
done
echo "$(date -Is) BATCH DONE"
