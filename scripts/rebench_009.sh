#!/usr/bin/env bash
# Experiment 009 final benchmarks (docs/experiments/009-*.md): n=4000, seat-rotated, deterministic RL.
# Resumable (skips jobs whose JSON exists), nice 19, few workers: meant for the HP, overnight.
# Usage: bash scripts/rebench_009.sh [WORKERS]   (repo root, ideally inside tmux)
# Checkpoints are the arms' fixed points, rsynced from the laptop and sha256-verified against
# results/009/league_manifest.json before launch.
set -u
cd "$(dirname "$0")/.."

N=4000
SEED=20261002
WORKERS=${1:-3}
PY=${PY:-.venv/bin/python}
CK=${CK:-runs/009}
mkdir -p results/009 logs/009

# name|mode|checkpoint  (priority order: baselines and the held-out probe first)
JOBS=(
  "baseline_thr_vs_rnd|match_threshold_vs_random|"
  "baseline_thr_vs_vn|match_von_neumann_vs_threshold|"
  "M20M_vs_thr|match_rl_vs_threshold|$CK/M/ckpt/ckpt_0020000000.zip"
  "C20M_vs_thr|match_rl_vs_threshold|$CK/C/ckpt/ckpt_0020000000.zip"
  "M20M_vs_vn|match_rl_vs_vonneumann|$CK/M/ckpt/ckpt_0020000000.zip"
  "C20M_vs_vn|match_rl_vs_vonneumann|$CK/C/ckpt/ckpt_0020000000.zip"
  "M20M_vs_rnd|match_rl_vs_random|$CK/M/ckpt/ckpt_0020000000.zip"
  "C20M_vs_rnd|match_rl_vs_random|$CK/C/ckpt/ckpt_0020000000.zip"
  "bc_vs_thr|match_rl_vs_threshold|$CK/bc/bc_init.zip"
  "bc_vs_rnd|match_rl_vs_random|$CK/bc/bc_init.zip"
  "bc_vs_vn|match_rl_vs_vonneumann|$CK/bc/bc_init.zip"
  "M10M_vs_thr|match_rl_vs_threshold|$CK/M/ckpt/ckpt_0010000000.zip"
  "M5M_vs_thr|match_rl_vs_threshold|$CK/M/ckpt/ckpt_0005000000.zip"
  "M10M_vs_rnd|match_rl_vs_random|$CK/M/ckpt/ckpt_0010000000.zip"
  "M5M_vs_rnd|match_rl_vs_random|$CK/M/ckpt/ckpt_0005000000.zip"
)

run_job() {
  IFS='|' read -r name mode ckpt <<<"$1"
  out="results/009/$name.json"
  log="logs/009/$name.log"
  [ -f "$out" ] && { echo "skip $name (done)"; return 0; }
  if [ -n "$ckpt" ] && [ ! -f "$ckpt" ]; then echo "$(date -Is) MISSING $ckpt for $name"; return 1; fi
  args=(--mode "$mode" --n "$N" --seed "$SEED" --out "$out")
  [ -n "$ckpt" ] && args+=(--checkpoint "$ckpt")
  echo "$(date -Is) start $name"
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    nice -n 19 "$PY" scripts/benchmark.py "${args[@]}" >"$log" 2>&1
  echo "$(date -Is) end   $name rc=$?"
}
export -f run_job
export N SEED PY CK

printf '%s\0' "${JOBS[@]}" | xargs -0 -P "$WORKERS" -I{} bash -c 'run_job "$1"' _ {} \
  2>&1 | tee -a logs/009/_batch.log
echo "$(date -Is) BATCH DONE" | tee -a logs/009/_batch.log
