# Seat-rotated re-benchmarks of the pre-2026-09-20 checkpoints (PRE-REGISTRATION)

**Date:** 2026-10-01 (pre-registered before any measured run; results pending)
**Notes:**
[gamekit#016 — Positional-advantage rotation](https://github.com/guidodinello/gamekit/blob/main/docs/research/016-positional-advantage-rotation.md),
[gamekit#009 — Longer runs / resume](https://github.com/guidodinello/gamekit/blob/main/docs/research/009-longer-runs-and-resume.md),
[gamekit#005 — Eval statistics](https://github.com/guidodinello/gamekit/blob/main/docs/research/005-eval-statistics.md)

## Hypotheses

- **H1 (plateau, gamekit#009):** the threshold-trained agent's "~84% plateau" ([log 003](003-threshold-training-plateau.md))
  is real, i.e. win rate vs Threshold stops improving late in the April run.
- **H2 (collapse, gamekit#001/#011):** the self-play checkpoints are materially worse than the threshold-trained
  ones vs Threshold ([log 004](004-april-selfplay-collapse.md), [log 005](005-june-threshold-mix-collapse.md)).
- **H3:** BC init and the random-trained checkpoint are far below the threshold-trained ones.
- **H4 (gamekit#016):** all pre-rotation numbers (84.0 / 85.3 / ~84 / 56.0 / 57.3 %) are inflated by the permanent
  Team-A mano advantage ([log 006](006-seat-rotation-deconfound.md)); rotated numbers will be lower.

## Config

`scripts/benchmark.py --mode <mode> --n 4000 --seed 20261001 --out results/008/<job>.json`, driven by
`scripts/rebench_008.sh` (3 workers, `nice -n 19`, `OMP_NUM_THREADS=1`, sequential priority order, resumable).

- Seat rotation mandatory (`gamekit.benchmark.run_arm`): each role plays Team A in 2000 matches, Team B in 2000.
- **n = 4000 full matches per pairing** (raised from the 1000 minimum after a local timing smoke showed
  ~24 matches/s vs Threshold; Wilson half-width ≈ 1.5 pp at p≈0.8).
- **Single seed 20261001 for every job** => identical deal sequences across checkpoints (paired deals).
- Wilson CIs from `gamekit.mc.wilson_interval` (in the result JSON, `by_role.*.win_rate_wilson_ci`); results are
  stamped with `git_commit`, `checkpoint_sha256(_12)`, `seed`, `mode`, `elapsed_s`.
- RL agents deterministic (`RLAgent` default).

## Harness deviation (found at launch, before any measured result)

The first launch hung: with seed 20261001, `truco_threshold_2000000` vs Threshold enters an endless Flor
raise cycle (`FLOR_CONTRA_RESTO` <-> `FLOR_CON_ENVIDO`, 0 pts on the table) inside one hand; `run_match`'s
200-hand valve cannot catch it. That batch was killed with no result written (logs kept on the HP in
`logs/008_aborted/`). Fix in `scripts/benchmark.py`: a hand exceeding `MAX_ACTIONS_PER_HAND = 2000` actions is
**voided** (scores unchanged, a fresh hand is dealt) and counted; `voided_hands` is stamped in each result JSON.
Locally, thr2M at n=100 voids 4 hands. Voided-hand counts are a **reported covariate**: they are an engine/policy
pathology (unbounded Flor re-raising) not fixed here, and any pairing with a high void rate is read with that caveat.

## Checkpoints (sha256_12 verified on both laptop and HP before launch)

| job | checkpoint | sha256_12 | provenance |
|---|---|---|---|
| thr5M | `truco_threshold_5000000.zip` (= `truco_threshold_final.zip`, identical hash) | 4acd5c3ee519 | April 2026 run (aux heads, MC) |
| thr4M | `truco_threshold_4000000.zip` | 1579b61d4a69 | April run |
| thr3.5M | `truco_threshold_3500000.zip` | 248d78d0a7fe | April run |
| thr3M | `truco_threshold_3000000.zip` | 2e6dd002c477 | June run (shaped reward) |
| thr2M | `truco_threshold_2000000.zip` | 9ac6ed9350b8 | June run — **not** the checkpoint behind the old 84.0/85.3% (overwritten, README caveat 2) |
| bc | `bc_init.zip` | 5500c81cae78 | 2026-04-05 BC warm start |
| sp5.5M / 5.6M / 6.1M / 6.6M | `truco_selfplay_{5500000,5600000,6100000,6600000}.zip` | fc9319546339 / 6f8ec82d4558 / 38803f0d1b90 / af6ca53f6f45 | June self-play mix run |
| spApril | `archive/truco_selfplay_april_collapsed.zip` | f6f53b4f2d20 | **Assumed** to be the "56%/57.3%" April collapse from its filename and log 004; not verified |
| random | `truco_random_final.zip` (= `truco_random_5000.zip`, identical hash) | 8d47d477dfae | April random-opponent run |

Not run: `threshold_500k–1.5M, 2.5M, 4.5M`, `archive/selfplay_final_smoketest`, VonNeumann arms (too slow).

## Jobs (priority order)

vs Threshold (`match_rl_vs_threshold`): thr5M, thr3.5M, thr2M, thr4M, thr3M, bc, sp5.5M, sp6.6M, spApril, random, sp5.6M, sp6.1M.
vs Random (`match_rl_vs_random`): thr5M, thr2M, bc, random.
Baseline (`match_threshold_vs_random`, no RL): calibrates what "vs Random" means.
If the HP is too slow, the tail of the list is dropped and recorded here as **deferred**, not silently omitted.

## Comparisons and decision rules (fixed now, before results)

1. **Plateau (H1), within-run:** Δ = win(thr5M) − win(thr3.5M) vs Threshold (both April run), two-proportion test
   (`gamekit.mc.two_proportion_test`; SE ≈ 0.9 pp at n=4000). **Plateau** if the 95% CI of Δ lies inside ±5 pp;
   **still climbing** if its lower bound is > 0; otherwise inconclusive. Shared deals make this test conservative.
2. **90% goal:** declared out of reach for thr5M if its Wilson upper bound < 90%.
3. **June 2M vs April 5M** is cross-run (different training runs sharing a filename scheme); reported but **not**
   used as plateau evidence.
4. **Self-play collapse (H2):** confirmed if every self-play checkpoint's CI upper bound is below thr5M's CI lower bound.
5. **BC / random (H3):** reported relative to 50% (parity with Threshold) and to thr5M.
6. **H4:** each rotated rate is compared against the corresponding legacy number; legacy numbers lacking `n` get no interval.
7. vs-Random results are a secondary sanity check, interpreted against the baseline job.

## Supersedes

- log 003's plateau claim (n=50/150), log 004's 56.0% / 57.3% figures, log 007's n=200 `truco_threshold_final` numbers
  (79.0% vs Threshold), and the README's pre-rotation win rates — once results are filled in.

## Environment

Commit: filled in from the result JSON `git_commit` (the pushed pre-registration commit, run on `homelab-hp`).

## Result

Pending — to be filled in from `results/008/*.json`.

## Verdict

Pending.
