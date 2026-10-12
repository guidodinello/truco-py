# Threshold-rollout VonNeumann: does calibrating the rollouts to rule-based play make the fair agent stronger?

**Status:** PRE-REGISTERED 2026-10-11, before any registered run. Not yet run.
**Date:** 2026-10-11
**Issue:** [#42](https://github.com/guidodinello/truco-py/issues/42) (roadmap Option 1, part of #46). Agent: `ThresholdRolloutVonNeumannAgent` (new). Technique note: [gamekit note 021](https://github.com/guidodinello/gamekit/blob/main/docs/research/021-decision-time-search.md). Baselines: [log 013](013-fair-vonneumann.md).

## Motivation

The fair VonNeumann of log 013 samples the hidden cards, but its rollouts are played by uniformly random choosers, so its EV estimates are calibrated against random play. `ThresholdRolloutVonNeumannAgent` changes exactly one thing: every seat in a rollout, the acting seat included, plays `ThresholdAgent`. The sampling, the EV rule, `r`, and the cache key are those of the fair agent (own cache namespace `vn-determinized-threshold-v1`). The measured quantity is how much that one change is worth.

Constraint carried over from #42: this agent models Threshold by construction, so it is **not independent of Threshold or of agents distilled from it** (C's teacher). It cannot replace the omniscient agent as the held-out opponent of logs 009-011.

## Hypothesis and gate

**H1 (primary, arm C):** with Threshold rollouts the fair agent beats the fair agent with random rollouts head to head, seat-rotated. The head-to-head isolates the rollout policy: same sampler, same `r`, same seeds, no cross-run comparison.

**Gate (fixed before any result).** `p` = win rate of the Threshold-rollout agent in arm C, n = 2000, Wilson 95 % interval:

- **PASS** if the lower bound is above 50 %.
- **FAIL** if the upper bound is below 50 %.
- **INCONCLUSIVE** otherwise (the interval contains 50 %). n = 2000 resolves about 4.5 points (Wilson half-width about 2.2 points); a smaller effect is reported as "no detectable difference at n = 2000", not as no effect.

One test, so no multiplicity adjustment. No ties are expected; any tie is reported and counted as a non-win for both sides.

**Secondary, descriptive only (no test, no decision rule):**

- **Arm A, vs Threshold:** win rate with Wilson 95 % CI, and its difference from the fair agent's 619/2000 (30.95 %, log 013 arm A) with a Newcombe 95 % CI for the difference of two independent proportions.
- **Arm B, vs the omniscient agent:** the same, against 686/2000 (34.3 %, log 013 arm B).
- These arms satisfy #42's "Done when" (benchmarked seat-rotated vs Threshold and vs the frozen VonNeumann, with Wilson intervals).
- The A and B differences are **cross-run comparisons** (different commit; same seed base, same engine, same gamekit benchmark path). Their opponents, seeds and deals match log 013's, but the pairing of random streams does not, so the Newcombe interval is the honest uncertainty, not a paired one.
- **Caveat on arm A:** the agent's rollout model is the actual opponent there, the best case for opponent modelling. A gain in A is partly "knows its opponent"; B and C are the less favourable checks.

## Config

- Code: the commit that merges this log (recorded in the Run log at launch). `scripts/benchmark.py` match modes (full matches, seat-rotated, `run_arm` + Wilson CIs). Launcher `scripts/run_014.sh`.
- **Arm C (primary):** `--mode match_von_neumann_threshold_rollout_vs_von_neumann_determinized` (`tr_vs_fair`)
- **Arm A:** `--mode match_von_neumann_threshold_rollout_vs_threshold` (`tr_vs_thr`)
- **Arm B:** `--mode match_von_neumann_threshold_rollout_vs_von_neumann_omniscient` (`tr_vs_omni`)
- `--n 2000` each (even, 1000 per seat), `--rollouts 20`, `--seed 20261002` (the seed base of logs 009 and 013), no `--cache_path` (in-memory EV cache, nothing persisted or shared between arms).
- Run on `homelab-hp` (4 cores, idle), **three workers, one per arm, in parallel**, `nice -n 19`, `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1`, in tmux session `truco-042` (one window per arm, `bash scripts/run_014.sh <arm>`), each logging to a file. One core is left free.
- Outputs: `results/014/<arm>.json` (stamped with seed, n, rollouts, mode, elapsed) and `logs/014/` in the repo checkout on the HP, never `/tmp`.
- Resume: an arm whose JSON exists is skipped; an interrupted arm restarts from zero (no per-match journal). Stop: `tmux send-keys -t truco-042:<window> C-c`.
- Analysis: win rates and Wilson 95 % CIs from `by_role` of the result JSONs, Newcombe for the two cross-run differences; nothing else is computed or tested.

## Environment

`homelab-hp`: 4 cores, about 5 GB RAM, Python 3.13.15, torch +cpu, **gamekit 0.3.0 @ `76c364b`** (the venv is hand-installed and is not re-synced; the same environment that produced log 013). `main` pins gamekit 0.4.0 (`cf34c9d`); the 0.3.0..0.4.0 diff touches `src/gamekit/rl/env.py` (one line) and no file on the benchmark path (`benchmark.py`, `seats.py`, `results.py`), so the deal sequence for a given seed is unchanged. The run uses `.venv/bin/python` directly, never `uv run`/`uv sync`.

## Timing (not results)

HP pilot (scratch `~/projects/truco-eval-data/pilot-042/`, branch commit `aaed91d`, `--seed 1`, n = 20 per arm, r = 20, nice 19, cold cache, **the three arms run in parallel**, 193 s wall in total):

| arm | n | wall (s) | s per match | extrapolated n = 2000 |
|---|---|---|---|---|
| B: vs omniscient | 20 | 98 | 4.9 | about 2.7 h |
| C: vs fair | 20 | 129 | 6.5 | about 3.6 h |
| A: vs Threshold | 20 | 193 | 9.7 | about 5.4 h |

Arms run concurrently, so the budget is the slowest arm: **about 5.4 h** (the caches warm, so probably a slight overestimate; other load on the HP could lengthen it). Peak memory is small (one process per arm).

**Disclosure.** The pilot printed win rates at seed 1, n = 20 (A 12/20, B 12/20, C 13/20 for the Threshold-rollout agent). They agree in direction with the hypothesis, are far too small to mean anything, and are not registered data.

## Deviations

None yet.

## Run log

Filled at launch and at the end.

## Result

Not run yet.

## Verdict

Not run yet. Gate as above: PASS / FAIL / INCONCLUSIVE on arm C only.
