# Fair VonNeumann: how much of the omniscient agent's strength was seeing the hands?

**Status:** PRE-REGISTERED 2026-10-09, before any registered run. RUN 2026-10-10 on the HP (one deviation, see below). Descriptive result filled in.
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

**1. Arm A crashed at about 1210 of 2000 matches (2026-10-10, 00:48 UTC); the sampler gets an exact fallback (PR #54).**

- **What happened.** `fair_vs_thr` died after about 2 h with `RuntimeError: no deal consistent with the public state after 200000 tries (player 3, has_flor=[True, True, True, False, True, True])`, raised by `draw_consistent_hands`. The last progress line was 1210/2000 (00:46:41); no partial result was written. The launcher moved on, so `fair_vs_omni` ran to completion (rc=0, 03:56 UTC) and is a valid, complete arm.
- **Cause: a rare tail of the sampler, not a consistency bug.** Five of the six seats held flor. The acceptance test is the engine's own `tiene_flor` on the same 3 cards that set `has_flor`, so the true deal always passes (a new test checks this at every decision of 300 random games). The joint rejection loop accepts a draw only if all five unseen hands have flor: flor is 15.5 % per hand (300k random deals), exactly 5 flors of 6 occurs in about 1.9e-4 of deals (so a few such deals are expected in 1200 matches), and a single try succeeds with probability of order 3e-5, or less once played cards pin a hand. The 200000-try cap is then reached with non-negligible probability.
- **Fix (PR #54).** The rejection loop, its RNG consumption and its cap are unchanged. Only where it used to raise, a fallback enumerates each seat's flor-consistent hands, draws one per seat uniformly and independently, and accepts when the hands are disjoint: exactly uniform over the jointly consistent deals, the same distribution the loop targets, and it terminates quickly. Tests cover the 5-flor-holder state (constructed explicitly), bit-identity with a verbatim copy of the old loop (same hands, tries and RNG state), and equal marginals between the two samplers. The old-code replay that would have reproduced the exact crash state was not run (the laptop was busy with another job); the constructed state stands in for it, so the exact failing state is not reproduced.
- **Arm B is unaffected.** No draw in arm B hit the cap (it completed), and every draw the loop accepts is bit-identical before and after the fix, so arm B's result is what the fixed code would also produce.
- **Arm A is rerun from zero** with the same seed and arguments on the fixed code. Its first 1210 or so matches replay identically (the fallback only runs where the old code raised), so the rerun differs from the crashed run only from the crash point on. The crashed run produced no result and nothing from it is used.


## Run log

- **Launch (first batch).** HP `homelab-hp`, commit `2c5b0d7`, `bash scripts/run_013.sh` in tmux `truco-050`, one worker, nice 19. Arm A started 2026-10-09 22:46:45 UTC and crashed at 2026-10-10 00:48:53 UTC (rc=1, see Deviation 1); arm B ran next, 00:48:53 to 03:56:43 UTC, rc=0, `elapsed_s` 11264 (3 h 08 min).
- **Fix and relaunch.** PR #54 merged (`1853f38`). The HP checkout went from `exp/013-prereg` to `main` at `1853f38` (fast-forward). Before launch: `tmux ls` showed only `catan-013`, `pgrep -af '[s]cripts/benchmark.py'` was empty, `results/013/fair_vs_omni.json` existed and `fair_vs_thr.json` did not. The crashed arm A log was renamed `logs/013/fair_vs_thr.crashed.log` (the launcher appends with `tee -a`). `bash scripts/run_013.sh` in tmux `truco-050` (batch log appended), arm A started 17:24:23 UTC; the script skipped arm B ("skip fair_vs_omni (done)").
- **End.** `end fair_vs_thr rc=0` and `BATCH DONE` at 2026-10-10 20:24:13 UTC, `elapsed_s` 10784 (3 h 00 min), against the pilot extrapolation of about 3.3 h per arm. No ties, `voided_hands` 0 in both arms. No traceback in either final log.
- **Slow step in the rerun.** Arm A matches 1210 to 1220 took about 9 min (19:20:22 to 19:29:39 UTC); the neighbouring 10-match steps took 25 to 60 s. The rerun therefore passed the old crash point (the crashed run died within about 2 min after its 1210 line, 00:46:41 to 00:48:53 UTC). The log has no warning or other message from the sampler and the fallback was not instrumented, so what the log shows is only this timing; it is consistent with the cap-exhausting rejection (about 200000 tries per decision) followed by the enumeration fallback running on that stretch, but it does not prove it.
- **Two commits.** The result JSONs are stamped `2c5b0d7` (arm B) and `1853f38` (arm A). This is fine because #54 left every draw the old rejection loop accepted bit-identical (tested against a verbatim copy of the old loop: same hands, tries and RNG state) and changed behaviour only where the old code raised. Arm B completed without raising, so the fixed code would have produced the same arm B. The agents, benchmark, seeds and arguments are otherwise identical.
- **Files.** `results/013/fair_vs_thr.json`, `results/013/fair_vs_omni.json`; logs `logs/013/` (`fair_vs_thr.log`, `fair_vs_omni.log`, the crashed `fair_vs_thr.crashed.log`, and the batch log `_batch.log`). Copied from the HP with scp.

## Result

Win rates and Wilson 95 % CIs from `by_role` of the result JSONs, n = 2000 each, 1000 per seat, r = 20, seed 20261002. No ties.

| arm | fair VN wins | fair win rate | Wilson 95 % CI | opponent win rate | z vs 50 % |
|---|---|---|---|---|---|
| A: fair vs Threshold | 619 / 2000 | 30.95 % | [28.96, 33.01] | Threshold 69.05 % [66.99, 71.04] | -24.1 |
| B: fair vs omniscient | 686 / 2000 | 34.3 % | [32.3, 36.4] | omniscient 65.7 % [63.6, 67.7] | -19.9 |

Seat check (both arms, by seat): arm A seat 0 49.75 %, seat 1 50.25 %; arm B seat 0 48.9 %, seat 1 51.1 %. No seat effect.

**The gap (arm B).** 50 % minus the fair agent's win rate is 15.7 points (Wilson CI of the fair rate gives [13.6, 17.7]). The fair agent loses a seat-rotated match to the omniscient one about two times in three.

**Direction check against the omniscient agent's Threshold results (preregistered item 3).** Threshold beat the omniscient agent 64.6 % [63.1, 66.1] (log 009, n = 4000) and 63.8 % (log 011, n = 10000), so the omniscient agent won 35.4 % and 36.2 %. The fair agent won 30.95 % [28.96, 33.01] against Threshold, below both, and its CI lies entirely below the 009 omniscient CI (35.4 %, [33.9, 36.9]). Removing the hidden-information advantage moved the agent's result against Threshold down by about 4.5 points (vs 009) and 5.3 points (vs 011).

Ordering read off the three pairings (descriptive): Threshold beats omniscient (about 64 %), omniscient beats fair (65.7 %), Threshold beats fair (69.05 %).

## Verdict

Descriptive only, as pre-registered (no test, no decision rule).

- Fair is clearly below omniscient: 34.3 % [32.3, 36.4], a gap of 15.7 points, far outside the 4.5-point resolution of n = 2000. The expected direction (fair < omniscient) holds. About 15.7 points of the omniscient agent's match strength against another VonNeumann come from seeing the hands.
- Fair against Threshold is 30.95 % [28.96, 33.01], below what the omniscient agent scored (about 36 %). The direction check says the hidden-information advantage was worth roughly 4.5 to 5.3 points against Threshold; it is smaller than the 15.7 points against the omniscient agent, as expected when the opponent also cheats.
- Threshold beats both VonNeumann variants. The baseline any fair VonNeumann improvement (#42) must be read against is 30.95 % against Threshold and 34.3 % against the omniscient agent.
- Caveats: one seed, r = 20 random rollouts, in-memory cache. The two arms ran at different commits (see Run log; bit-identical by #54). Logs 009 to 011 stay valid only as results against the perfect-information opponent.
