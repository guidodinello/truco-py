#!/usr/bin/env bash
# Experiment 014 (docs/experiments/014-*.md): Threshold-rollout VonNeumann (#42), ONE arm per call.
# n=2000, seat-rotated, r=20, seed base of log 009, in-memory cache, one worker, nice 19.
# Arms: tr_vs_fair (primary), tr_vs_thr, tr_vs_omni. Meant for the HP, one tmux window per arm:
#   tmux new -d -s truco-042 -n C 'bash scripts/run_014.sh tr_vs_fair'
#   tmux new-window -t truco-042 -n A 'bash scripts/run_014.sh tr_vs_thr'
#   tmux new-window -t truco-042 -n B 'bash scripts/run_014.sh tr_vs_omni'
# Runs in the foreground, so `tmux send-keys -t truco-042:<window> C-c` stops it.
# Resume = skip an arm whose JSON exists; an interrupted arm restarts from zero.
set -u
cd "$(dirname "$0")/.."

N=2000
SEED=20261002
PY=${PY:-.venv/bin/python}

case "${1:-}" in
  tr_vs_fair) mode=match_von_neumann_threshold_rollout_vs_von_neumann_determinized ;;
  tr_vs_thr)  mode=match_von_neumann_threshold_rollout_vs_threshold ;;
  tr_vs_omni) mode=match_von_neumann_threshold_rollout_vs_von_neumann_omniscient ;;
  *) echo "usage: $0 tr_vs_fair|tr_vs_thr|tr_vs_omni" >&2; exit 2 ;;
esac
name=$1
out="results/014/$name.json"
mkdir -p results/014 logs/014

[ -f "$out" ] && { echo "skip $name (done)"; exit 0; }
if pgrep -af "[s]cripts/benchmark.py --mode $mode " >/dev/null; then
  echo "refuse $name: already running" >&2; exit 1
fi

echo "$(date -Is) start $name" | tee -a logs/014/_batch.log
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH="$PWD" \
  nice -n 19 "$PY" scripts/benchmark.py --mode "$mode" --n "$N" --seed "$SEED" --rollouts 20 \
  --out "$out" 2>&1 | tee -a "logs/014/$name.log"
rc=${PIPESTATUS[0]}
echo "$(date -Is) end   $name rc=$rc" | tee -a logs/014/_batch.log
exit "$rc"
