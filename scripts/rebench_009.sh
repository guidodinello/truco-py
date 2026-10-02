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

# Chunk boundaries overshoot by < one rollout (4096 steps), so a "fixed point" is the first
# checkpoint at or after N steps: fixed_at <arm> <N>  ->  path (empty if none yet).
fixed_at() {
  local f s
  for f in $(ls "$CK/$1"/ckpt/ckpt_*.zip 2>/dev/null | sort); do
    s=$((10#$(basename "$f" .zip | cut -d_ -f2)))
    [ "$s" -ge "$2" ] && { echo "$f"; return; }
  done
}
M5=$(fixed_at M 5000000);  M10=$(fixed_at M 10000000);  M20=$(fixed_at M 20000000)
C20=$(fixed_at C 20000000)

# name|mode|checkpoint  (priority order: baselines and the held-out probe first)
JOBS=(
  "baseline_thr_vs_rnd|match_threshold_vs_random|"
  "baseline_thr_vs_vn|match_von_neumann_vs_threshold|"
  "M20M_vs_thr|match_rl_vs_threshold|$M20"
  "C20M_vs_thr|match_rl_vs_threshold|$C20"
  "M20M_vs_vn|match_rl_vs_vonneumann|$M20"
  "C20M_vs_vn|match_rl_vs_vonneumann|$C20"
  "M20M_vs_rnd|match_rl_vs_random|$M20"
  "C20M_vs_rnd|match_rl_vs_random|$C20"
  "bc_vs_thr|match_rl_vs_threshold|$CK/bc/bc_init.zip"
  "bc_vs_rnd|match_rl_vs_random|$CK/bc/bc_init.zip"
  "bc_vs_vn|match_rl_vs_vonneumann|$CK/bc/bc_init.zip"
  "M10M_vs_thr|match_rl_vs_threshold|$M10"
  "M5M_vs_thr|match_rl_vs_threshold|$M5"
  "M10M_vs_rnd|match_rl_vs_random|$M10"
  "M5M_vs_rnd|match_rl_vs_random|$M5"
)

run_job() {
  IFS='|' read -r name mode ckpt <<<"$1"
  out="results/009/$name.json"
  log="logs/009/$name.log"
  [ -f "$out" ] && { echo "skip $name (done)"; return 0; }
  case "$name" in baseline_*) ;; *) [ -f "$ckpt" ] || { echo "$(date -Is) MISSING checkpoint for $name"; return 1; } ;; esac
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
