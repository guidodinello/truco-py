# League over the exp 009 checkpoints: round-robin ratings

**Status:** PRE-REGISTERED 2026-10-05, before any measured run (the only earlier runs are the laptop timing runs under
"Timing (not results)"). RUN on the HP 2026-10-05/06; results below. Descriptive only, no verdict scored.
**Date:** 2026-10-05
**Note:** [gamekit#022 — League ratings: anchored Bradley-Terry/Elo over a round-robin, with the win matrix alongside](https://github.com/guidodinello/gamekit/blob/main/docs/research/022-league-ratings.md)
(module `gamekit.league`, gamekit#38). This is the first truco league, run after the engine fixes (#26) that the note
asked for.

## Motivation

[Log 009](009-retrain-mixed-pool.md) ranked its checkpoints by win rate against one opponent at a time
(Threshold, VonNeumann, Random), and the opponents disagree on the order: C-final beats M-final against VonNeumann
(64.1 % vs 56.8 %) but the two tie against Threshold (91.2 % vs 91.8 %). A league rates every agent against every other on one
scale and shows the pairwise matrix next to it, including the checkpoints against each other, which log 009 never played.

## Use of the ratings, and what this is not

**This experiment is descriptive.** It has no hypothesis test, no decision rule, no pass/fail threshold and no verdict
ladder. The ratings are used for:

1. a common Elo scale (Threshold = 0) for the seven 009 checkpoints plus the two baselines;
2. reading off whether the 009 "C beats M against VonNeumann" ordering also shows up head to head (C20 vs M20) and in the ratings;
3. looking for significant 3-cycles in the win matrix (gamekit's cycle report), and for non-transitivity between near-equal checkpoints;
4. a fixed roster, seed scheme and anchor, so a later league can add agents without invalidating these pairings.

Every cell is reported with its Wilson 95 % interval; none is tested. The C20-vs-M20 cell is *not* a registered test.
Nothing decided here changes any 009 conclusion, and any follow-up experiment must pre-register its own rule.

## Roster (9 agents, 36 pairings)

Fixed points are the ones in the log 009 Run log (first checkpoint at or after 5M / 10M / 20M steps). Full hashes:
`results/010/manifest.json`; the driver refuses to start unless every file matches it.

| name | file | sha256_12 |
|---|---|---|
| M5 | `runs/009/M/ckpt/ckpt_0005002240.zip` | f66c396e4930 |
| M10 | `runs/009/M/ckpt/ckpt_0010002432.zip` | 7c80bfd7eef1 |
| M20 | `runs/009/M/ckpt/ckpt_0020000768.zip` | 3a8309bf2850 |
| C5 | `runs/009/C/ckpt/ckpt_0005001216.zip` | 7e42419b58b8 |
| C10 | `runs/009/C/ckpt/ckpt_0010001408.zip` | 6b796317a244 |
| C20 | `runs/009/C/ckpt/ckpt_0020000256.zip` | 62b60962114d |
| bc_init | `runs/009/bc/bc_init.zip` | 8280da87016b |
| threshold | `ThresholdAgent` (**anchor, Elo 0**) | n/a |
| random | `RandomAgent` | n/a |

M5, M10, M20, C20 and bc_init hashes equal the ones stamped in `results/009/*.json`; C5 and C10 were never benchmarked
in 009, so theirs are first recorded here. **VonNeumann is excluded** (too slow on the HP). The roster is the orchestrator's suggested one, unchanged.

## Config

Fixed now; any difference at run time is a deviation and is listed under "Deviations".

- Code: `scripts/league_010.py` (driver), `scripts/launch_010.sh` (HP launcher), `tests/test_league_010.py`. Commit: `dbaabc8` (the merge of #34).
- **Unit:** full `TrucoMatch` (default rules), RL agents deterministic, exactly as the 009 finals.
- **Seat reduction:** `num_seats=2` *team slots*, as in `scripts/benchmark.py`: slot 0 is Team A's three players, slot 1 is Team B's,
  each filled with 3 copies of one agent. gamekit#022's multi-player A-B-A-B lineup (an agent holds N/2 individual seats) is the
  same construction with the team as the seat, so the Bradley-Terry reading `P(a wins) = pi_a / (pi_a + pi_b)` carries over.
  `run_arm` rotates the slots, so each agent plays Team A in half of the matches (mano advantage cancels).
  `gamekit.league` passes `play` an already-rotated lineup; the driver places it as-is and does not rotate again (tested).
- **Matches per pairing: n = 10000** (even), **seed 20261005** (fresh; not the 009 seed 20261002). Per-pairing engine/driver seeds
  are gamekit's `pairing_seeds(seed, a, b)`, independent of the roster.
- Random/Threshold agents are rebuilt per pairing, seeded from the pairing's driver seed (role a: offsets 0,2,4; role b: 1,3,5),
  so a resumed pairing never depends on run order. RL models are deterministic.
- **Ratings:** `summarize_league(..., anchor="threshold", anchor_rating=0, prior_draws=1, n_bootstrap=1000, bootstrap_seed=0, alpha=0.05)`.
  The summary is computed from the pairing files by `python -m scripts.league_010 summarize` and includes the win matrix with
  Wilson CIs, the BT prediction and residual per cell, ties per pairing, and the significant-edge 3-cycle report.
- **CLI:** `bash scripts/launch_010.sh <commit> league 10000 3`, i.e.
  `python -m scripts.league_010 run --name league --n 10000 --workers 3`, nice 19, one thread per worker, in tmux `truco-010-league`.
  One process per pairing (`run_league(agents=[a, b], anchor=a)` writes the same file and config hash as a full-roster run).
  Resumable: a finished pairing file is skipped, a pairing file with a different config hash is refused.
- **Output:** `results/010/league/<a>__vs__<b>.json` (36 files), `results/010/league/league.json`, logs in `logs/010/`.

## Timing and expected wall time

Laptop timing runs (n=400, 2 concurrent single-thread processes, `--name timing` into a scratch directory, not in `results/`):

| pairing class | count | matches/s (laptop) |
|---|---|---|
| RL vs RL (`C20__vs__M20`) | 21 | 29.5 |
| RL vs Threshold (`C20`, `M20`) | 7 | 64.2 to 65.8 |
| RL vs Random (`C20`) | 7 | 102 |
| Threshold vs Random | 1 | not timed (about as fast as RL vs Random or faster; 4 s per 4000 in 009) |

Laptop CPU time per match across the league: 21/29.5 + 7/65 + 7/102 + 1/100 = 0.90 s per unit of n, so n=10000 is about 9.0e3 CPU-s.
On the HP at an **assumed 4x slowdown per core (not measured)**, with 3 workers: 9.0e3 x 4 / 3 = 12.0e3 s = **about 3.3 h**
(5 h if the real factor is 6). The cross-machine check below measures the real factor, and n is re-checked against it before launch;
if the measured rate implies more than about 8 h, n is reduced to 6000 and the change is logged as a deviation. The HP also runs
GitHub Actions runners, so the estimate is unvalidated.

## Cross-machine check (gate for the HP results)

Before the HP league counts, one RL-vs-RL pairing, **C20 vs M20 at n=200, league name `xcheck`, seed 20261005**, is run on the laptop and on the HP.
It passes if the wins, the ties and the sha256 of the per-game winning-slot list (logged by the driver) are all identical.
If it fails, the HP league does not count; the league is run on the laptop instead and the failure is logged under Deviations.
The `xcheck` files are discarded afterwards and never enter the league.

## Environment

- **Laptop:** HDD venv `truco-py-retrain-venv` (the one that ran the 009 finals): torch 2.11.0+cu128 (the lock), gamekit 0.3.0 at
  76c364b (includes `gamekit.league`, a7cb5ae), GPU not used.
- **HP (`homelab-hp`):** CPU-only, 4 cores, no AVX2 (AVX only), about 5.5 GB RAM free. **Environment difference:** torch 2.11.0+cpu
  installed from the PyTorch CPU index with all other packages from the lock (`--no-deps`), so it is **not** the lock's cu128 wheel. The
  cross-machine check is the evidence that the difference does not change the results. Recorded at launch: commit `dbaabc8`, Python 3.13.15, torch 2.11.0+cpu, gamekit 0.3.0 at 76c364b (same as the laptop).

## Timing (not results)

Throwaway laptop runs while sizing n (scratch directory, different n, never in `results/010/`): C20 vs M20, C20 vs Threshold,
M20 vs Threshold and C20 vs Random at n=400, one seed. The output printed C20 winning 40.2 % of the C20-vs-M20 matches, so this author saw one
coarse number for that cell before launch. It changes nothing: there are no decision rules to bias, and the league reruns that pairing at n=10000.

## Deviations

| date | what | why |
|---|---|---|
| 2026-10-05 | HP measured about 7.1x slower per core than the laptop (31.55 vs 4.46 matches/s, C20 vs M20, 1 worker), not the assumed 4x | the timing assumption was unmeasured. The re-estimate was about 7.3 h (3 workers), under the 8 h line, so **n stayed 10000**; the 6000 fallback was not used |
| 2026-10-05 | Untracked exp 008 outputs on the HP (`logs/008`, `results/008`) moved to `~/truco-py-hp-008-backup/`, nothing deleted | they blocked the checkout of the merge commit; no effect on 010 |
| 2026-10-05 | HP venv rebuilt (torch 2.11.0+cpu, others from the lock with `--no-deps`); the old `.venv-old` was deleted after pytest passed on the HP (167 tests) | planned environment difference, see Environment |
| 2026-10-05 | PR #34 was committed with `SKIP=mypy` (the hook runs bare `uv run mypy`, outside the HDD venv); mypy was run directly and passed | process note, no effect on results |

## Run log

- Launch: `bash scripts/launch_010.sh dbaabc8 league 10000 3`, tmux `truco-010-league` on `homelab-hp`, nice 19, one thread per worker,
  **start 2026-10-05T23:28:52Z**, **exit 0 at 2026-10-06T06:15:41Z**. Wall **6 h 47 m**, against the 7.3 h re-estimate (3.3 h in the
  pre-registration, which used the unmeasured 4x). No errors or tracebacks in `logs/010/league.log`.
- Cross-machine check (gate): C20 vs M20, n=200, seed 20261005, `xcheck`: **passed**. Laptop and HP gave identical wins (80 for C20, 120 for M20),
  0 ties, config hash `38b17aeb8a5a` and winners sha256 `4e7760c5...` (full value in the launch session log). The xcheck files were deleted on both machines.
- The HP driver verified the 7-checkpoint manifest at launch (log: `manifest verified: 7 checkpoints`); it was re-verified on the laptop at analysis.
- Results pulled with rsync; for all 36 pairing files the stamp was re-derived and matched: names cover every pair of the roster, seed 20261005,
  n 10000, `num_seats` 2, `config_hash` equal to gamekit's hash of that config, engine/driver seed bases equal to `pairing_seeds`, commit `dbaabc8`,
  and the two roles' wins sum to 10000 (no ties anywhere).
- Committed: `results/010/league/` (36 pairing files + `league.json`, 152 KB) and `logs/010/league.log` (388 KB).
  `league.json` was regenerated with `python -m scripts.league_010 summarize` (the in-run copy is the known race).

## Result

### Ratings (Elo, threshold = 0, 95 % bootstrap CI, 1000 resamples)

| agent | Elo | 95 % CI |
|---|---|---|
| M20 | 353.2 | [348.9, 357.2] |
| M10 | 333.4 | [329.6, 337.2] |
| C20 | 308.3 | [304.4, 312.2] |
| C10 | 305.4 | [301.3, 309.3] |
| M5 | 298.9 | [294.9, 302.9] |
| C5 | 285.4 | [281.5, 288.9] |
| threshold | 0.0 | [0.0, 0.0] |
| bc_init | -13.3 | [-17.1, -9.7] |
| random | -171.7 | [-175.9, -167.2] |

### Win matrix (row beats column, % of 10000 decisive matches; Wilson 95 % half-width is 0.4 to 1.0 points in every cell, the per-cell intervals are in `results/010/league/league.json`)

| row \ col | M20 | M10 | C20 | C10 | M5 | C5 | threshold | bc_init | random |
|---|---|---|---|---|---|---|---|---|---|
| M20 | - | 55.1 | 58.9 | 58.2 | 56.1 | 60.3 | 92.5 | 88.7 | 86.7 |
| M10 | 44.9 | - | 55.4 | 57.0 | 53.8 | 59.7 | 90.4 | 87.5 | 88.0 |
| C20 | 41.1 | 44.6 | - | 49.2 | 48.6 | 53.4 | 90.5 | 90.6 | 92.9 |
| C10 | 41.8 | 43.0 | 50.8 | - | 47.9 | 53.2 | 90.7 | 87.5 | 93.1 |
| M5 | 43.9 | 46.2 | 51.4 | 52.1 | - | 54.8 | 85.1 | 83.5 | 84.4 |
| C5 | 39.7 | 40.3 | 46.6 | 46.8 | 45.2 | - | 88.3 | 86.5 | 94.1 |
| threshold | 7.5 | 9.6 | 9.5 | 9.3 | 14.9 | 11.7 | - | 59.9 | 87.3 |
| bc_init | 11.3 | 12.6 | 9.4 | 12.5 | 16.6 | 13.5 | 40.1 | - | 83.0 |
| random | 13.4 | 12.0 | 7.1 | 6.9 | 15.6 | 5.9 | 12.7 | 17.0 | - |

Ties: none in any of the 36 pairings. Significant 3-cycles (gamekit cycle report): **none**.
Source: `results/010/league/league.json` (`python -m scripts.league_010 summarize`, all numbers above are copied from it).

### Reading (descriptive, no test)

- **Ladder.** Every RL checkpoint rates 285 to 353 Elo above Threshold; bc_init is 13 below it and Random 172 below. By checkpoint,
  the M line rates M20 > M10 > M5 and the C line C20 ~ C10 > C5 (C20 and C10 CIs overlap, 304 to 312 vs 301 to 309).
- **The 009 "C beats M against VonNeumann" ordering does not show up here.** Head to head M beats C at every matched step:
  M5 vs C5 54.8 %, M10 vs C10 57.0 %, M20 vs C20 58.9 % (C20 wins 41.1 %, Wilson [40.1, 42.0]). In the ratings M20 (353) and M10 (333) sit above C20 (308) with non-overlapping CIs.
  This is a different opponent set from 009 (no VonNeumann here), so it does not contradict the 009 numbers; it is what these 36 pairings show.
- **Within a line, later checkpoints are not always better head to head.** M20 beats M10 55.1 % and M10 beats M5 53.8 %, but C20 vs C10 is 49.2 % (the interval spans 50 %) and C20 beats C5 only 53.4 %.
  M5 slightly beats C10 (52.1 %) and C20 (51.4 %), although M5 rates below both on the Elo scale, because Elo also uses their results against the baselines.
- **Baseline cells fit the one-dimensional scale worst.** The largest Bradley-Terry residuals are all Random cells:
  Random vs Threshold wins 12.7 % against a predicted 27.1 % (residual -0.145), Random vs bc_init 17.0 % vs 28.7 %, and Random vs M5 15.6 % vs 6.2 %.
  M-line agents beat Random less often than they beat Threshold (M20: 86.7 % vs 92.5 %; M5: 84.4 % vs 85.1 %), while C-line agents beat Random at least as often as Threshold (C5: 94.1 % vs 88.3 %).
  The anchored rating puts Random near the bottom, but the matrix shows the M and C lines treat it differently. No significant 3-cycle appears.
- **Seat order.** In the C20-vs-M20 file the two slot positions win 49.9 % / 50.1 %, i.e. the rotation removed the mano effect, as designed.


## Verdict

Descriptive only, as pre-registered: no verdict is scored for gamekit#022 and no 009 conclusion is changed. Recorded: the league ran as
specified (36 pairings, n=10000 each, no ties, no deviation that affects results; cross-machine check passed), and it rates the M line above the C line at every
matched checkpoint, with no significant 3-cycles. Whether M or C is better against VonNeumann-style opponents was not measured here. Any follow-up
(for example adding VonNeumann to the roster, or more checkpoints) must pre-register its own rule.
