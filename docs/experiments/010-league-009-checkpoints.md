# League over the exp 009 checkpoints: round-robin ratings

**Status:** PRE-REGISTERED 2026-10-05, before any measured run. The only runs so far are the laptop timing runs
listed under "Timing (not results)". Results and verdict are placeholders.
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

- Code: `scripts/league_010.py` (driver), `scripts/launch_010.sh` (HP launcher), `tests/test_league_010.py`. Commit: filled at launch.
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
  cross-machine check is the evidence that the difference does not change the results. Commit, Python and package versions are filled at launch.

## Timing (not results)

Throwaway laptop runs while sizing n (scratch directory, different n, never in `results/010/`): C20 vs M20, C20 vs Threshold,
M20 vs Threshold and C20 vs Random at n=400, one seed. The output printed C20 winning 40.2 % of the C20-vs-M20 matches, so this author saw one
coarse number for that cell before launch. It changes nothing: there are no decision rules to bias, and the league reruns that pairing at n=10000.

## Deviations

| date | what | why |
|---|---|---|

## Run log

(filled at launch)

## Result

(not yet run)

## Verdict

Descriptive only: no verdict is scored for gamekit#022 from this run alone beyond a record of the ratings and matrix.
