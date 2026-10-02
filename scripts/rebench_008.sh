#!/usr/bin/env bash
# Experiment 008 batch runner: seat-rotated re-benchmarks (docs/experiments/008-*.md).
# Sequential-priority job list, 3 workers, nice 19, resumable (skips jobs whose JSON exists).
# Usage: bash scripts/rebench_008.sh   (run from the repo root, ideally inside tmux)
set -u
cd "$(dirname "$0")/.."

N=4000
SEED=20261001
WORKERS=3
PY=.venv/bin/python
mkdir -p results/008 logs/008

# name|mode|checkpoint  (priority order)
JOBS=(
  "thr5M_vs_thr|match_rl_vs_threshold|checkpoints/truco_threshold_5000000.zip"
  "thr3.5M_vs_thr|match_rl_vs_threshold|checkpoints/truco_threshold_3500000.zip"
  "thr2M_vs_thr|match_rl_vs_threshold|checkpoints/truco_threshold_2000000.zip"
  "thr4M_vs_thr|match_rl_vs_threshold|checkpoints/truco_threshold_4000000.zip"
  "thr3M_vs_thr|match_rl_vs_threshold|checkpoints/truco_threshold_3000000.zip"
  "bc_vs_thr|match_rl_vs_threshold|checkpoints/bc_init.zip"
  "sp5.5M_vs_thr|match_rl_vs_threshold|checkpoints/truco_selfplay_5500000.zip"
  "sp6.6M_vs_thr|match_rl_vs_threshold|checkpoints/truco_selfplay_6600000.zip"
  "spApril_vs_thr|match_rl_vs_threshold|checkpoints/archive/truco_selfplay_april_collapsed.zip"
  "random_vs_thr|match_rl_vs_threshold|checkpoints/truco_random_final.zip"
  "sp5.6M_vs_thr|match_rl_vs_threshold|checkpoints/truco_selfplay_5600000.zip"
  "sp6.1M_vs_thr|match_rl_vs_threshold|checkpoints/truco_selfplay_6100000.zip"
  "thr5M_vs_rnd|match_rl_vs_random|checkpoints/truco_threshold_5000000.zip"
  "thr2M_vs_rnd|match_rl_vs_random|checkpoints/truco_threshold_2000000.zip"
  "bc_vs_rnd|match_rl_vs_random|checkpoints/bc_init.zip"
  "random_vs_rnd|match_rl_vs_random|checkpoints/truco_random_final.zip"
  "baseline_thr_vs_rnd|match_threshold_vs_random|"
)

run_job() {
  IFS='|' read -r name mode ckpt <<<"$1"
  out="results/008/$name.json"
  log="logs/008/$name.log"
  [ -f "$out" ] && { echo "skip $name (done)"; return 0; }
  args=(--mode "$mode" --n "$N" --seed "$SEED" --out "$out")
  [ -n "$ckpt" ] && args+=(--checkpoint "$ckpt")
  echo "$(date -Is) start $name"
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    nice -n 19 "$PY" scripts/benchmark.py "${args[@]}" >"$log" 2>&1
  echo "$(date -Is) end   $name rc=$?"
}
export -f run_job
export N SEED PY

printf '%s\0' "${JOBS[@]}" | xargs -0 -P "$WORKERS" -I{} bash -c 'run_job "$1"' _ {} \
  2>&1 | tee -a logs/008/_batch.log
echo "$(date -Is) BATCH DONE" | tee -a logs/008/_batch.log
