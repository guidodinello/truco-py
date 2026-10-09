# Fair VonNeumann: how much of the omniscient agent's strength was seeing the hands?

**Status:** PRE-REGISTERED 2026-10-09, before any registered run. Result and Verdict not yet filled.
**Date:** 2026-10-09
**Issue:** [#50](https://github.com/guidodinello/truco-py/issues/50). Agents: `DeterminizedVonNeumannAgent` (#51, fair) and `OmniscientVonNeumannAgent` (renamed in #52; logs 009-011 cite it as "VonNeumann"). Log 012 is claimed by #49 (human baseline).

## Motivation

The VonNeumann of logs 009-011 rolls out from a copy of the true deal, so it sees every hand (#50). Those logs stay valid only as results against that perfect-information opponent.
The fair variant samples the hidden cards before each rollout and cannot see them. How much weaker is it? The gap is the measured quantity: it says how much of the omniscient agent's strength came from seeing the cards, and it is the baseline any fair VonNeumann improvement (#42) must be read against.

## Hypothesis and status

**Expectation (directional, not a test with a decision rule):** fair < omniscient. The size of the gap is what is measured.

**Descriptive only (no test, no decision rule, no multiplicity adjustment):**

1. Arm A, fair vs Threshold: win rate with Wilson 95 % CI.
2. Arm B, fair vs omniscient: win rate with Wilson 95 % CI. The gap is 50 % minus the fair agent's win rate (no ties are expected).
3. Direction check against the omniscient agent's Threshold results: Threshold beat the omniscient agent 64.6 % [63.1, 66.1] (log 009 baseline, n = 4000, seed 20261002) and 63.8 % (log 011 league pairing, n = 10000), so the omniscient agent won about 36 % against Threshold. Report whether fair vs Threshold lies above or below that, i.e. whether removing the hidden-information advantage moved the agent's result against Threshold, and in which direction. No new omniscient-vs-Threshold arm is run: logs 009 and 011 already measured it at r = 20 with seat rotation.

If fair vs omniscient lands at or above 50 % (CI containing or exceeding 0.5), that is reported as "no detectable gap at n = 2000", not as a refutation of the mechanism: n = 2000 resolves a gap of roughly 4.5 points (Wilson half-width about 2.2 points) and the cheating benefit may be smaller than that.

## Config

- Code: main at `e42c1a0` (after #52). `scripts/benchmark.py`, the `match` modes (full matches, seat-rotated, `run_arm` + Wilson CIs).
- **Arm A:** `--mode match_von_neumann_determinized_vs_threshold`
- **Arm B:** `--mode match_von_neumann_determinized_vs_von_neumann_omniscient`
- `--n 2000` each (even, so seats rotate evenly: 1000 per seat), `--rollouts 20`, `--seed 20261002` (the seed base of log 009), no `--cache_path` (in-memory EV cache, nothing persisted, nothing shared between arms or runs).
- Run on `homelab-hp` (4 cores; catan league 013 uses 3 of them), **one worker**, `nice -n 19`, `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1`. The two arms run one after the other in tmux session `truco-050` (`scripts/run_013.sh`), logging to a file.
- Outputs: `results/013/<arm>.json` (stamped with commit, seed, n, rollouts) and `logs/013/`, in the repo checkout on the HP, never `/tmp`. The pilot's scratch outputs are under `~/projects/truco-eval-data/pilot-050/` and are not registered data.
- Analysis: win rates and Wilson 95 % CIs read from the result JSONs (`by_role`); nothing else is computed or tested. Ties are reported if any occur.

## Timing (not results)

HP pilot (scratch `~/projects/truco-eval-data/pilot-050/`, `--seed 1`, n = 20 per arm, r = 20, one worker, nice 19, cold cache, catan-013 running on 3 other cores):

| arm | n | wall (s) | s per match |
|---|---|---|---|
| fair vs Threshold | 20 | 119.5 | 5.97 |
| fair vs omniscient | 20 | 111.8 | 5.59 |

Extrapolated to n = 2000: about 3.3 h per arm, **about 6.5 h for both, run one after the other** (the cache warms, so this is probably a slight overestimate; the GitHub runner or catan load could lengthen it). Peak memory is small (one process).

**Disclosure.** The pilot printed win rates at seed 1, n = 20 (fair vs Threshold 9/20 = 45 %, fair vs omniscient 8/20 = 40 %). They agree in direction with the expectation, are far too small to mean anything, and are not registered data.

## Deviations

None yet.

## Run log

Filled in when the run finishes.

## Result

(not yet run)

## Verdict

(not yet run)
