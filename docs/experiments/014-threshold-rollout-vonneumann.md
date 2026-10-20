# Threshold-rollout VonNeumann: does calibrating the rollouts to rule-based play make the fair agent stronger?

**Status:** PRE-REGISTERED 2026-10-11, before any registered run. RUN 2026-10-12 on the HP (no deviations). Result and verdict filled in: arm C **PASS**.
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

None. Three arms, modes, `n`, `r`, seed base, commit and launcher are as registered. One labelling change after the run, requested by the owner: the Newcombe cross-run differences for arms A and B (listed under the secondary items) are reported below as **exploratory**, not part of the verdict.

## Run log

- **Launch.** HP `homelab-hp`, commit `fe2ddc3` (the merge of the pre-registration, #57), `bash scripts/run_014.sh <arm>` in tmux `truco-042`, one window per arm (C `tr_vs_fair`, A `tr_vs_thr`, B `tr_vs_omni`), nice 19, one worker each. All three started 2026-10-12 00:40:39 UTC.
- **End.** All three arms `rc=0`: B at 04:07:55 UTC (`elapsed_s` 12431, 3.45 h), C at 04:52:41 (15117, 4.20 h), A at 05:55:49 (18905, 5.25 h). Pilot extrapolation was about 2.7 h, 3.6 h and 5.4 h. Budget was the slowest arm, 5.25 h against 5.4 h.
- **Integrity.** Every JSON is stamped `git_commit` `fe2ddc3`, `seed` and both seed bases 20261002, `n_games` 2000 (1000 per seat), `rollouts` 20, the registered `mode`. `voided_hands` 0 in all arms, no ties, no traceback or warning in any log. Wilson intervals recomputed from the win counts agree with the JSON values.
- **Environment.** HP venv gamekit 0.3.0 @ `76c364b`, as registered.
- **Files.** `results/014/{tr_vs_fair,tr_vs_thr,tr_vs_omni}.json`; logs `logs/014/` (`tr_vs_fair.log`, `tr_vs_thr.log`, `tr_vs_omni.log`, `_batch.log`). Copied from the HP with scp.

## Result

Win rates and Wilson 95 % CIs of the Threshold-rollout agent from `by_role` of the result JSONs, n = 2000 each, 1000 per seat, r = 20, seed 20261002. No ties.

| arm | TR wins | TR win rate | Wilson 95 % CI | opponent win rate | z vs 50 % |
|---|---|---|---|---|---|
| **C (primary): vs fair random-rollout** | 1115 / 2000 | 55.75 % | [53.56, 57.91] | 44.25 % [42.09, 46.44] | 7.27 |
| A: vs Threshold | 1117 / 2000 | 55.85 % | [53.66, 58.01] | Threshold 44.15 % [41.99, 46.34] | 7.40 |
| B: vs omniscient | 1036 / 2000 | 51.80 % | [49.61, 53.98] | omniscient 48.20 % [46.02, 50.39] | 2.28 |

Seat check (seat 0 win rate over both roles): C 50.75 %, A 47.85 %, B 50.6 %. No seat effect in C and B; A is 2.15 points under 50 % in seat 0, descriptive only.

**Cross-run differences (EXPLORATORY, not part of the verdict).** Against the fair agent's log 013 results, with the Newcombe 95 % interval for two independent proportions. Different commit, same seed base and engine, unpaired random streams, so the interval is the honest uncertainty. No decision rule is attached to these.

| arm | TR | log 013 fair | difference | Newcombe 95 % CI |
|---|---|---|---|---|
| A: vs Threshold | 55.85 % | 619 / 2000 = 30.95 % | +24.90 pp | [+21.90, +27.84] |
| B: vs omniscient | 51.80 % | 686 / 2000 = 34.3 % | +17.50 pp | [+14.46, +20.49] |

## Verdict

**H1 (arm C): PASS.** The Threshold-rollout agent won 1115 of 2000 seat-rotated matches against the fair random-rollout agent, 55.75 %, Wilson 95 % [53.56, 57.91]. The lower bound is above 50 %, so the gate registered before any result is met. n = 2000, one seed, r = 20, in-memory cache.

Arms A and B are descriptive only and do not enter the verdict. They satisfy #42's "Done when" (benchmarked seat-rotated against Threshold and the frozen omniscient VonNeumann, with Wilson intervals).

- Caveat carried from the pre-registration: in arm A the rollout model is the actual opponent, the best case for opponent modelling, so A is the most favourable of the three arms.
- The agent models Threshold by construction. It is not independent of Threshold or of agents distilled from it (C's teacher) and cannot replace the omniscient agent as the held-out opponent of logs 009-011.
- Exploratory reading, not a finding: the B interval [49.61, 53.98] contains 50 %, so against the omniscient agent the data do not separate the Threshold-rollout agent from even. Not registered and not tested.
