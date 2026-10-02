# Seat-rotated re-benchmarks of the pre-2026-09-20 checkpoints

**Date:** 2026-10-01 (pre-registered before any measured run) / 2026-10-02 (results)
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

Commit `d84352b` (stamped in every result JSON), run on `homelab-hp` (4 cores, shared with CI runners),
2026-10-01 23:28 UTC to 2026-10-02 00:25 UTC, 3 workers, `nice -n 19`. torch 2.5.1+cu121 (CPU).

## Result

Source: `results/008/*.json` (17 files) and `logs/008/` (committed). All 17 verified: `git_commit` = `d84352b…`,
`checkpoint_sha256_12` matches the table above (baseline has no checkpoint), `n_games` = 4000, `seed` = 20261001,
`voided_hands` present. Win rate is the first-named role's share of the 4000 matches (seat-rotated, 2000 each seat;
no ties are possible in a match). Voided hands are hands, not matches (see Harness deviation).

### vs Threshold (`match_rl_vs_threshold`)

| pairing | wins | win rate | Wilson 95% CI | voided hands (per 100 matches) |
|---|---|---|---|---|
| thr5M (April, =final) | 3204/4000 | 80.1% | [78.8%, 81.3%] | 13 (0.33) |
| thr4M (April) | 3123/4000 | 78.1% | [76.8%, 79.3%] | 18 (0.45) |
| thr3.5M (April) | 3110/4000 | 77.8% | [76.4%, 79.0%] | 4 (0.10) |
| thr3M (June) | 3159/4000 | 79.0% | [77.7%, 80.2%] | 69 (1.73) |
| thr2M (June) | 3136/4000 | 78.4% | [77.1%, 79.6%] | 55 (1.38) |
| bc_init | 2052/4000 | 51.3% | [49.8%, 52.8%] | 0 (0.00) |
| sp5.5M | 3139/4000 | 78.5% | [77.2%, 79.7%] | 77 (1.93) |
| sp5.6M | 3029/4000 | 75.7% | [74.4%, 77.0%] | 85 (2.12) |
| sp6.1M | 2877/4000 | 71.9% | [70.5%, 73.3%] | 49 (1.23) |
| sp6.6M | 2800/4000 | 70.0% | [68.6%, 71.4%] | 66 (1.65) |
| spApril (archive, assumed 56% ckpt) | 2154/4000 | 53.8% | [52.3%, 55.4%] | 17 (0.42) |
| random_final | 2041/4000 | 51.0% | [49.5%, 52.6%] | 31 (0.78) |

### vs Random (`match_rl_vs_random`) and baseline

| pairing | wins | win rate | Wilson 95% CI | voided hands (per 100 matches) |
|---|---|---|---|---|
| thr5M | 2148/4000 | 53.7% | [52.2%, 55.2%] | 0 (0.00) |
| thr2M | 2423/4000 | 60.6% | [59.1%, 62.1%] | 0 (0.00) |
| bc_init | 1887/4000 | 47.2% | [45.6%, 48.7%] | 0 (0.00) |
| random_final | 2640/4000 | 66.0% | [64.5%, 67.5%] | 0 (0.00) |
| **baseline: Threshold agent (no RL)** | 2088/4000 | 52.2% | [50.7%, 53.7%] | 0 (0.00) |

### Decision rules applied as pre-registered

1. **Plateau, thr5M vs thr3.5M (both April run).** Δ = 80.1% − 77.75% = **+2.35 pp**, SE 0.91 pp, 95% CI
   **[+0.56, +4.14] pp** (`two_proportion_test`: z=2.58, p=0.0100). Rule "plateau if the CI lies inside ±5 pp":
   **met**. Rule "still climbing if the lower bound is > 0": **also met**. The pre-registered rules were not
   mutually exclusive and this result satisfies both; no precedence was fixed in advance, so this log does not
   pick one. Descriptively: a small positive gain (≤ 4.1 pp, 4M→5M +2.0 pp, p=0.026) over 1.5M steps, nowhere near
   a jump. Not an "inconclusive" outcome under the stated wording; it is an under-specified rule.
2. **90% reachable:** thr5M's Wilson upper bound is **81.3% < 90%** → for this checkpoint, 90% is rejected.
3. **Self-play collapse (rule: every self-play CI upper bound < thr5M CI lower bound 78.8%):** **not satisfied.**
   sp5.5M's upper bound is 79.7% (78.5% vs 80.1%, overlapping). The other three June self-play checkpoints
   (75.7% / 71.9% / 70.0%, uppers 77.0 / 73.3 / 71.4) and spApril (53.9%, upper 55.4) clear the bar. Descriptively: the
   June mix checkpoints do **not** collapse to the ~56% of log 004/005 (they are 70–78%, declining with steps);
   only `archive/truco_selfplay_april_collapsed` (53.9%) shows a collapse, consistent with the legacy 56.0%/57.3%
   if that file is the one those numbers came from (still an assumption).
4. **BC / random vs 50% and the Threshold baseline.**
   - vs Threshold: bc_init 51.3% [49.8, 52.9] and random_final 51.0% [49.5, 52.6]: both CIs include 50% (parity with Threshold).
   - vs Random: bc_init **47.2% [45.6, 48.7] (below 50%)**; random_final 66.0% [64.5, 67.5] (the only one clearly above).
   - Baseline Threshold vs Random: **52.2% [50.7, 53.8]**, so "vs Random" is a weak yardstick; thr5M 53.7% [52.2, 55.2] and
     thr2M 60.6% are close to or only modestly above it. Threshold-trained agents are exploiting Threshold far more
     than they beat Random.
5. **June 2M vs April 5M (cross-run, descriptive only):** 78.4% [77.1, 79.7] vs 80.1% [78.8, 81.3]; Δ = +1.7 pp
   (z=1.87, p=0.061). Different training runs, not plateau evidence.
6. **Versus the legacy numbers (H4), descriptive:** `truco_threshold_final`/thr5M: legacy ~84% (n=50, [71.5, 91.7])
   → 80.1%, inside the legacy CI so the data cannot show a shift; log 007's post-rotation 79.0% (n=200,
   [72.8, 84.1]) agrees with 80.1%. The legacy 84.0%/85.3% were of the overwritten June 2M file, so they have no
   valid counterpart here. Legacy 56.0% (n=150) → spApril 53.9%. Direction is consistent with a confound removal
   of a few points, but it is not demonstrated.

### Voided-hand rates

Voids are an engine liveness bug (audit A-01), not a measurement: 0 in all vs-Random and baseline jobs, and
4–85 hands per 4000 matches vs Threshold (0.1–2.1 per 100). Highest: sp5.6M 2.12, sp5.5M 1.93, thr2M 1.38, thr3M 1.73, sp6.6M 1.65.
Lowest: thr3.5M 0.10, thr5M 0.33, thr4M 0.45. Voids are not scored, so they shrink the effective sample slightly and are not random with respect to the checkpoint (the
self-play and June checkpoints void most). The plateau comparison involves two of the lowest-void jobs (13 and 4).

## Verdict

- **gamekit#009 (longer runs when the curve hasn't bent), H1:** **inconclusive as pre-registered.** The plateau and
  "still climbing" rules both fire (Δ +2.35 pp, CI [+0.56, +4.14]); the honest reading is a slow, small gain that is far
  from 90% (thr5M upper bound 81.3%). The original "~84% plateau" claim is superseded: the best checkpoint is ~80%.
- **90% goal:** **rejected for thr5M** (upper bound 81.3% < 90%).
- **gamekit#001/#011 (self-play collapse), H2:** **not confirmed by the pre-registered rule** (sp5.5M overlaps thr5M);
  the April collapse reproduces on `spApril` (53.9%), the June mix checkpoints decline to 70–78% without collapsing to ~56%.
- **H3:** vs Threshold, BC and random-trained are at parity (~51%), not "far below"; vs Random, bc_init loses (47.2%).
  **Rejected as stated.**
- **gamekit#016 (positional-advantage rotation), H4:** **inconclusive.** Rotated numbers are a few points below the
  legacy ones, consistent with the confound, but legacy CIs are too wide (and the 2M file was overwritten) to show it.
- **gamekit#005 (eval statistics):** n=4000 with Wilson CIs resolves ~±1.3 pp, enough to decide the questions above
  that the n=50/150 numbers could not; **supports** the note's recommendation.

## Disclosure: these numbers are from the PRE-FIX engine

Since launch, the rules audit merged (PR #14: `docs/rules.md`, `docs/engine-rules-audit.md`) and the engine is
being fixed separately on `fix/engine-rules-audit`. **008 measures what these checkpoints learned and play under the
pre-fix rules at `d84352b`.** They were also trained under those rules, so these results characterise
(checkpoint, buggy engine) pairs; they are not rules-correct skill estimates, and re-running after the fix will
change them. Audit findings that can affect these numbers:

- **A-01** (flor raises never terminal, ladder goes backwards): causes the voided hands above.
- **A-02** (contra flor al resto pays last bidder's shortfall): up to 30-point swing on a hand.
- **A-03** (`VALE_CUATRO` legal directly over plain `TRUCO`): affects every truco.
- **A-04** (envido raises uncapped/unbounded): overshoot near the target; same liveness class as A-01.
- **A-05** (envido tie always goes to team A) and **A-06** (flor tie always to team A): small, and a residual team-A
  bias that seat rotation cancels in aggregate but that still distorts the learned policies.
- **A-07** (`[parda, parda, B]` awarded to team A): rare (~0.03% of hands).
- **A-08** (contested flor pays a flat 3/5 regardless of flors held): ~3.9% of deals.
- **A-11** (no «irse al mazo»/«pasar» during card play): a real strategic action is absent from the action space.
- A-09 (FOLD on plain flor; negligible for rational agents) and A-10 (missing «con flor» ladder; restricts the
  action space, no outcome error) are not expected to move these numbers materially.

**Seed/deal caveat (audit Appendix B).** The pre-registration says the shared seed gives "identical deal sequences
across checkpoints" (paired deals) and that the independent-samples test is therefore conservative. That is **not
guaranteed**: `benchmark.py` reuses one `TrucoGame` whose deck is shuffled in place, so a deal depends on every earlier
`reset`, and the number of resets depends on the agents' play. Deals diverge across checkpoints after the first match.
Treat the pairings as independent samples: the two-proportion test is the appropriate (not conservative) test, and
the pre-registered rule outcomes above were computed with it. Each job is repeatable as a whole run in one process.
