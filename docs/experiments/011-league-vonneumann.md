# League with VonNeumann added: is the M/C order opponent-dependent?

> VonNeumann in this log = the omniscient (perfect-information) variant, renamed in #52.

**Status:** RUN 2026-10-08 on the HP (amended before any measured run, see below). Primary test: **replicates** (C beats M against VonNeumann again). Result and Verdict filled below.
**Date:** 2026-10-07
**Note:** [gamekit#022](https://github.com/guidodinello/gamekit/blob/main/docs/research/022-league-ratings.md) (`gamekit.league`), as in [log 010](010-league-009-checkpoints.md).

## Motivation

Two earlier results look opposed:

- [Log 009](009-retrain-mixed-pool.md), H2: against VonNeumann, **C-final beat M-final** (64.1 % vs 56.8 %, n=4000 each, p < 0.001).
- [Log 010](010-league-009-checkpoints.md), which had no VonNeumann: **M beats C head to head** at every matched step
  (M5-C5 54.8 %, M10-C10 57.0 %, M20-C20 58.9 %), and M rates above C on the Elo scale.

These are not contradictory (the order can depend on the opponent, and one Bradley-Terry scale cannot represent that), but they have never
been measured on one scale. This experiment adds VonNeumann to the 010 roster, replicates the 009 VonNeumann cell with fresh seeds, and puts VonNeumann
on the 010 rating scale.

## Hypothesis and status of each part

**Primary, confirmatory (one test, alone in its family):** replication of 009's H2 contrast against VonNeumann.

- `d = winrate(C20 vs VonNeumann) - winrate(M20 vs VonNeumann)`, each win rate over the n = 10000 decisive matches of its pairing.
- Test: two-proportion z-test (pooled), two-sided, alpha = 0.05. No other test is in the family, so no multiplicity correction.
- Decision rule (fixed now):
  - **Replicates:** d > 0 and p < 0.05 (C beats M against VonNeumann again).
  - **Reverses:** d < 0 and p < 0.05 (M beats C against VonNeumann).
  - **Inconclusive:** p >= 0.05.
- Power: both arms have n = 10000, and the 009 values are p of about 0.64 and 0.57. The standard error of d at p = 0.6 is
  sqrt(2 x 0.24 / 10000) = 0.69 pp, so the minimum detectable effect at 80 % power is about 1.9 pp, and the 009 effect (7.3 pp) is detected with power above 99.9 %.
  A true effect that shrank below 1.9 pp would likely land in "inconclusive".

**Descriptive only (no test, no decision rule):**

1. VonNeumann's Elo on the 010 scale (anchor threshold = 0) and the full 10x10 win matrix with Wilson 95 % intervals.
2. The sign and size of C minus M against VonNeumann at 5M and 10M steps (C5 vs M5, C10 vs M10, as win-rate differences with CIs, not tested).
3. Where VonNeumann sits among the checkpoints in the ratings, the Bradley-Terry residuals of the VonNeumann cells, and gamekit's significant 3-cycle report.
   A cycle involving VonNeumann, M and C would be the league-level form of "the order depends on the opponent". It is reported, not tested.

The league does not arbitrate "which is better, M or C". The 010 head-to-head (M ahead) and a C-over-M result against VonNeumann can both hold, and either outcome here is a
fact about the matrix. Nothing decided here changes a 009 or 010 conclusion; any follow-up must pre-register its own rule.

## Roster (10 agents, 45 pairings, 9 new)

The 9 agents of log 010 (M5, M10, M20, C5, C10, C20, bc_init, threshold = anchor at Elo 0, random; same files, same hashes, manifest
`results/010/manifest.json`) plus **vonneumann**: `VonNeumannAgent(n_rollouts=20, seed=driver seed + offset)`, as in log 009, in-memory EV cache only
(`cache_path=None`), built per pairing so no state crosses pairings or runs.

## Config

- Code: `scripts/league_010.py` (now takes `--baselines` and `--manifest`; the 010 defaults are unchanged), `scripts/launch_011.sh`, `tests/test_league_010.py`. Commit: filled at launch.
- **Reuse of exp 010.** The 36 pairing files of log 010 (n = 10000, seed 20261005) are **copied unchanged** into `results/011/league/`; their sha256 are in
  `results/011/010_pairings.sha256` and are verified at launch (`sha256sum -c`). This is valid because gamekit's pairing config hash covers only
  `(a, b, num_seats, n, seed)` and `pairing_seeds(seed, a, b)` does not depend on the roster, so a pairing file is the same whether or not VonNeumann is in the league.
  The 010 results directory is not touched.
- **New pairings:** the 9 `<agent>__vs__vonneumann` pairings, **n = 10000 each, seed 20261005** (the same seed as 010; each pairing's engine/driver
  seeds come from `pairing_seeds`, so they are fresh relative to log 009's seed 20261002).
- Unit and seat reduction as in log 010: full `TrucoMatch`, deterministic RL agents, `num_seats=2` team slots with 3 copies of each agent, slots rotated by gamekit.
- **Ratings:** `summarize_league(..., anchor="threshold", anchor_rating=0, prior_draws=1, n_bootstrap=1000, bootstrap_seed=0, alpha=0.05)` over all 45 files, via
  `python -m scripts.league_010 summarize --results-dir results/011`. The 010 ratings are not refit or edited; the 011 ratings of the old agents will move slightly because VonNeumann is added.
- **Run (SUPERSEDED by the amendment below):** on the laptop, from the commit that merges this PR: `bash scripts/launch_011.sh 9` (tmux `truco-011-league`, nice 19, 9 workers, one thread each). Resumable.
- **No overlap with catan #46 (SUPERSEDED: the run moves to the HP, see the amendment; the launcher guard stays)** (which measures latency): the launcher refuses to start while `experiments.search_eval` is running, and the run is started only when no catan job is
  running and none is scheduled to start during it. A start or run overlapping a catan job is logged as a deviation.
- **No HP, no cross-machine check (SUPERSEDED: the run is on the HP and has a cross-machine gate, see the amendment):** every new pairing runs on the laptop, in the HDD venv that produced the 010 analysis.

## Timing (not results)

Laptop (i5-13500HX, 20 threads), HDD venv, scratch directories, `--seed 1`, never in `results/011/`. C20 and M20 are the slow and fast ends of the 009 VonNeumann rates.

| run | n | workers | matches/s |
|---|---|---|---|
| C20 vs VonNeumann | 100 | 1 | 1.89 |
| M20 vs VonNeumann | 100 | 1 | 2.29 |
| C20 vs VonNeumann | 600 | 1 | 1.60 at 100 games, 1.79 at 600 (the cache warms) |
| all 9 VonNeumann pairings | 100 | 9 | 0.77 (C5) to 1.65 (random); first run 0.72 to 1.53 |

Peak RSS per process was 675 MB at n = 10, 100 and 600, so no cache growth was visible; 9 workers are about 6 GB of 15 GB RAM. The VonNeumann cache at n = 10000 was not
measured, so the log is checked for memory use during the run.

**Expected wall time:** the 9 pairings run in parallel, so wall time is that of the slowest (C5, C20, C10 at about 0.8 matches/s with 9 workers running):
10000 / 0.8 = 12,500 s, **about 3.5 h** (4 h ceiling; less once faster pairings finish and free cores, and once the cache has warmed, since the single-worker rate rose from 1.6 to 1.8).
With 20 threads and 9 busy workers the per-worker rate is well below the single-worker one (hyperthread sharing), so the estimate is declared unvalidated.

**Disclosure.** (1) The timing runs print win rates, so this author saw coarse versions of the primary cells before this pre-registration: C20 vs VonNeumann 60.0 % (n=100)
and 64.2 % (n=600), M20 vs VonNeumann 46.0 % (n=100), all at `--seed 1`. They agree in direction with log 009; they are not registered data and the league reruns those pairings at n=10000 with
seed 20261005. There is no rule to bias beyond the one above, which is fixed. (2) Catan #46's agent ran its pytest suite (about 1 core, ~3 min, around 19:25 to 19:30 local) during the
first 9-worker timing and the start of the n=600 run. The 9-worker timing was repeated with the machine to itself (the table's last row); the effect was small (slowest 0.72 to 0.77 matches/s).
No catan job ran during the other timing runs (checked with `pgrep` before each run).

## Amendment: the run moves to the HP (2026-10-07, before any measured run)

**Why.** Catan #46 needs about 26 h of daytime laptop time, and a laptop run of about 4 h would come out of it. The HP is always on and idle. The owner decided to run exp 011 there
continuously, with no nightly stops (resume per pairing already exists). **No measured 011 game had been played when this was written**; the only runs are the timing runs
(`--seed 1`, scratch directories) listed here and above. The owner's decision is the reason; the data gave none.

**What changes (and nothing else).**
- **Machine:** HP, torch 2.11.0+cpu, **3 workers**, nice 19, one thread each: `PY=.venv/bin/python bash scripts/launch_011.sh 3`, tmux `truco-011-league`, from the commit that merges this amendment.
- **n stays 10000.** The hypothesis, the decision rule, the power statement, the seed 20261005, the roster, the 36 copied 010 files, the summary configuration and the descriptive list are **unchanged**.
- **Cross-machine gate (new, includes VonNeumann).** `M20__vs__vonneumann`, **n = 40**, league name `xcheck`, run on the laptop and on the HP with
  `python -m scripts.league_010 run --name xcheck --n 40 --seed 1 --workers 1 --baselines threshold,random,vonneumann --pairs M20__vs__vonneumann --results-dir <scratch>`.
  It passes if the wins, the ties, the config hash and the logged `winners_sha256` are all identical. If it fails, the HP results do not count and the run does not start.
  It uses **seed 1, not 20261005**: pairing seeds do not depend on n, so with the registered seed the xcheck's 40 games would be the first 40 games of the confirmatory M20-vs-VonNeumann cell, a peek at
  registered data. Seed 1 checks determinism just as well. (Log 010's xcheck used the registered seed; this avoids repeating that.) The xcheck files are deleted afterwards.
- **Laptop leg of the xcheck** runs only while `pgrep -af experiments.search_eval` is empty (polled until it is), and the check is noted in the Run log.

**HP timing** (scratch directory, `--seed 1`, nice 19, `OMP_NUM_THREADS=1`, n = 40, cold VonNeumann cache; peak RSS 278 MB per process):

| run | workers | matches/s |
|---|---|---|
| C20 vs VonNeumann | 1 | 0.39 |
| M20 vs VonNeumann | 1 | 0.54 |
| C5, C20, C10 vs VonNeumann together | 3 | 0.43, 0.32, 0.31 |

For VonNeumann pairings the HP is about 4x slower per core than the laptop's single-worker cold rate (0.39 vs 1.6 for C20), less than the 7x seen for RL-vs-RL in log 010.
**Expected wall time.** Per-pairing HP rates under 3 workers are taken from the laptop's clean 9-worker rates (C5 0.77, C10 0.84, C20 0.78, M5 1.34, M10 1.04, M20 1.19, bc_init 1.01,
threshold 1.09, random 1.65) scaled by the ratio of the HP 3-worker C rate (about 0.35) to the laptop's (about 0.80), i.e. x 0.44. That gives per-pairing times of 3.8 h (random)
to 8.2 h (C5, C20) at n = 10000. List scheduling over 3 workers in the driver's order (C10, C20, C5, M10, M20, M5, bc_init, random, threshold) gives a makespan of about **19 to 20 h**;
total CPU is about 56 h. **Unvalidated:** the GitHub runner shares the HP, the VonNeumann cache warms (rates rose about 10 % over 600 games on the laptop), and the estimate rests on a ratio. If the
slowest pairing is still unfinished after 30 h, the run is checked, not stopped. Peak memory at n = 10000 was not measured; 3 x 0.3 GB leaves ample room of the 5 GB, and memory is watched during the run.

**Disclosure.** The HP timing runs printed coarse VonNeumann win rates at seed 1, n = 40 (C20 60.0 %, M20 40.0 %, C5 72.5 %, C10 52.5 %); they are not registered data and the league reruns those pairings
at n = 10000 with seed 20261005. The exp 010 outputs on the HP (untracked files that blocked the checkout of main) were byte-compared with the committed copies (36 pairing files and the log identical;
`league.json` differs because the committed one was regenerated by `summarize`), then moved to `~/truco-py-hp-010-backup/`, nothing deleted.

## Environment

Laptop (superseded for the run, still the xcheck's second machine and the analysis machine): HDD venv `truco-py-retrain-venv`, torch 2.11.0+cu128 (the lock), gamekit 0.3.0 at 76c364b, GPU not used. Commit, python and package versions are recorded at launch.
The copied 010 pairings were produced on the HP (torch 2.11.0+cpu) and passed log 010's cross-machine check.
**HP (the run machine after the amendment):** `homelab-hp`, 4 cores (no AVX2), about 5 GB RAM, one GitHub runner; Python 3.13.15, torch 2.11.0+cpu,
gamekit 0.3.0 at 76c364b, no nvidia/triton packages. torch +cpu is now also the lock's `cpu` extra (#38); the venv was installed by hand for log 010 and is not re-synced.

## Deviations

| date | what | why |
|---|---|---|
| 2026-10-07 | Run machine changed from the laptop to the HP, 3 workers; cross-machine gate added (pre-run amendment, see above) | the owner needs the laptop's daytime hours for catan #46; no measured game had been played |
| 2026-10-08 | none after the run started | the run was not stopped, restarted or altered; the laptop rebooting overnight did not touch it (it ran on the HP) |

## Run log

- **Cross-machine gate (passed).** `M20__vs__vonneumann`, n = 40, `--seed 1`, league `xcheck`, 1 worker. Laptop and HP gave identical results: M20 16 wins, VonNeumann 24, no ties,
  config hash `331a07813175`, `winners_sha256` `bbd6e6c11c33776e5d2990130780113975a11e716ee2d008715e9aedf6cc9c04`. The laptop leg ran after `pgrep -af experiments.search_eval` was empty (catan's smoke had finished).
  The xcheck files were deleted on both machines. (The xcheck's 16/24 is at seed 1, not registered data.)
- **Launch.** HP `homelab-hp`, commit `6322efb`, `PY=.venv/bin/python bash scripts/launch_011.sh 3`, tmux `truco-011-league`, nice 19, 3 workers. Start 2026-10-08 00:41:33 UTC.
  The 36 copied 010 files passed `sha256sum -c`; manifest verified (7 checkpoints); "9 pairings to play (n=10000, seed=20261005, workers=3)".
- **Progress.** Pairings finished in this order (UTC, 2026-10-08): C20 08:25, C10 08:57, C5 09:03, M10 14:00, M20 14:01, M5 14:05, random 17:39, threshold 19:02, bc_init 20:04.
- **End.** `league league: all pairings done`, `exit 0` at 2026-10-08 20:04:08 UTC. **Wall time 19 h 22 min** against the amendment's unvalidated estimate of 19 to 20 h.
  The log has no warning, error or traceback. The `cp -n` warnings printed by the launcher at start are harmless (the 36 files were verified by `sha256sum -c` right after).
  Memory: 3 workers at about 280 MB RSS each in the first minutes with about 5 GB free; no later RSS sample was kept, and no worker died or restarted.
- **Provenance check at pull.** 45 pairing files, all n = 10000, no ties. The 9 VonNeumann files are stamped commit `6322efb`; the 36 copied files keep their 010 stamp (`dbaabc8`) and are byte-identical to log 010's (`sha256sum -c` ok).
  Pulled with rsync into the worktree, summarized on the laptop with `python -m scripts.league_010 summarize --results-dir results/011` (HDD venv; no matches played on the laptop for the analysis).
  Files: `results/011/league/` (45 pairings + `league.json`), `logs/011/league.log`.

## Result

### Primary (confirmatory, one test)

| cell | agent wins / 10000 | win rate | Wilson 95 % |
|---|---|---|---|
| C20 vs VonNeumann | 6352 | 63.52 % | [62.57, 64.46] |
| M20 vs VonNeumann | 5704 | 57.04 % | [56.06, 58.01] |

`d = 63.52 - 57.04 = +6.48 pp`, 95 % CI of d (unpooled) [+5.13, +7.83]. Pooled two-proportion z = **9.36**, two-sided **p < 1e-15** (far below 0.05).
Decision rule as registered: d > 0 and p < 0.05, so **replicates**.
For reference, 009 had C 64.1 %, M 56.8 % (d = 7.3 pp, n = 4000 each); the fresh seed 20261005 gives 63.5 % and 57.0 %, within about 0.6 pp on each side.

### Ratings (Elo, threshold = 0, 95 % bootstrap CI, 1000 resamples; all 45 files)

| agent | Elo | 95 % CI |
|---|---|---|
| M20 | 289.3 | [285.9, 292.6] |
| M10 | 274.6 | [271.1, 277.8] |
| C20 | 255.9 | [252.6, 258.9] |
| C10 | 254.1 | [250.8, 257.2] |
| M5 | 243.3 | [239.8, 246.5] |
| C5 | 237.1 | [233.9, 240.2] |
| vonneumann | 112.5 | [109.1, 115.9] |
| threshold | 0.0 | [0.0, 0.0] |
| bc_init | -23.7 | [-27.1, -20.4] |
| random | -192.8 | [-196.9, -188.6] |

### VonNeumann column of the win matrix (agent beats VonNeumann, % of 10000; Wilson half-width about 1 pt)

| agent | C5 | C10 | C20 | M5 | M10 | M20 | threshold | bc_init | random |
|---|---|---|---|---|---|---|---|---|---|
| beats VonNeumann | 64.7 | 64.3 | 63.5 | 58.1 | 59.9 | 57.0 | 63.8 | 50.4 | 18.0 |
| Bradley-Terry predicted | 67.2 | 69.3 | 69.5 | 68.0 | 71.8 | 73.5 | 34.4 | 31.3 | 14.7 |

(Predicted = `1 / (1 + 10^(-(R_agent - R_VN) / 400))` from the ratings above; the other 36 cells are as in log 010 and are in `results/011/league/league.json`.)
Ties: none in any of the 45 pairings. Significant 3-cycles (gamekit cycle report): **none** (`cycles` is empty).

### Reading (descriptive, no test)

- **C minus M against VonNeumann at the other steps** (win-rate differences, unpooled 95 % CI, not tested): 5M **+6.63 pp** [+5.28, +7.98] (C5 64.68 vs M5 58.05); 10M **+4.42 pp** [+3.08, +5.76] (C10 64.32 vs M10 59.90);
  20M +6.48 pp [+5.13, +7.83] (the primary cell). C is ahead of M against VonNeumann at all three steps, by 4 to 7 points.
- **The order is opponent-dependent, and the single Elo scale cannot show it.** Head to head M still beats C (M20 vs C20 58.9 %, M10 vs C10 57.0 %, M5 vs C5 54.8 %, unchanged from log 010) and rates above it
  (M20 289 vs C20 256), yet against VonNeumann C beats M at every step. The two facts sit in the same matrix.
- **VonNeumann rates 112 Elo above Threshold, but Threshold beats VonNeumann 63.8 %** (the model predicts 34.4 %, residual +0.29, the largest in the league).
  Against VonNeumann, Threshold (63.8 %) does as well as C20 (63.5 %) and better than every M checkpoint (57.0 to 59.9 %), even though M20 beats Threshold 92.5 % and C20 beats it 90.5 %.
  The one-dimensional scale places VonNeumann by its results against the other eight agents (it beats Random 82.0 %, bc_init 49.6 %/50.4 %, and loses to every RL checkpoint and to Threshold).
- **Bradley-Terry residuals of the other VonNeumann cells:** the M cells are the next worst (M20 predicted 73.5 %, observed 57.0 %, residual -0.164; M10 -0.119; M5 -0.099), the C cells are mild (-0.025 to -0.060),
  bc_init vs VonNeumann is +0.19 (50.4 % against 31.3 %), Random +0.03.
- **Rating shifts from adding VonNeumann.** The old agents moved down on the scale relative to 010 (M20 353 -> 289, C20 308 -> 256, M5 299 -> 243, C5 285 -> 237), most likely because Threshold, the anchor, does as well against VonNeumann as the C agents and better than the M agents (not tested); the order among the six checkpoints is unchanged (M20 > M10 > C20 > C10 > M5 > C5). Treat the 011 and 010 scales as different scales.
- **No tie, no significant 3-cycle**, in particular none involving VonNeumann, M and C, so the opponent-dependence appears as a poor fit of one cell group (residuals above), not as a gamekit-detectable cycle.

## Verdict

**Primary (confirmatory): replicates.** `d = +6.48 pp`, z = 9.36, p < 0.05 by a wide margin: C20 beats M20 against VonNeumann, as 009's H2 found, with fresh seeds and n = 10000 per cell.
The minimum detectable effect was about 1.9 pp, so this is not a borderline call.

Descriptive, no verdict: M is ahead of C head to head (log 010) and C is ahead of M against VonNeumann (this log), at 5M, 10M and 20M; both hold at once, so which is "better" depends on the opponent
and is not answered by either. VonNeumann rates 112.5 Elo (above Threshold, below all six checkpoints), with a large misfit against Threshold. Nothing here changes a 009 or 010 conclusion; any follow-up
(for example whether the effect is VonNeumann-specific, or a rating model with an opponent-dependent term) must pre-register its own rule.
