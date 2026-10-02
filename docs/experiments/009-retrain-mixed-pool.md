# Retraining on the fixed engine: BC warm start + PPO against a mixed opponent pool

**Status:** PRE-REGISTERED 2026-10-02, before any measured run. Phase 0 (smoke and throughput) is
done and recorded below; those runs are not results. "Result" and "Verdict" are empty on purpose.
**Date:** 2026-10-02 (owner decisions D1-D9, (a), (b) recorded)
**Notes:** gamekit#001 (opponent mix), #002 (BC fine-tune lr), #009 (fixed-point trend, resume),
#011 (collapse detection), #013 (run-scoped pool), #022 (team-consistent opponents)

## Motivation

[Log 008](008-seat-rotated-rebenchmarks.md): threshold-trained agents beat Threshold 80.1 % [78.8, 81.3]
but Random only 53.7 % [52.2, 55.2], against a Threshold-vs-Random baseline of 52.2 % (n=4000).
That looked like exploitation of one opponent. All pre-#26 numbers describe a different game (65 actions,
old checkpoints refused), so everything is retrained. Phase 0 found the 52.2 % baseline is void: on the
rebuilt engine Threshold beats Random 87.5 % (see "Phase 0").

## Owner decisions (Guido, 2026-10-02)

| | Decision |
|---|---|
| D1 | Opponent *team* per episode: Threshold 0.4 / Random 0.2 / own snapshot 0.4 (uniform over the run's pool); snapshot every 1M steps |
| D2 | Partner seats: the latest own snapshot (BC init before the first one) |
| D3 | Control arm **C**: Threshold-only opponent team, otherwise identical to arm **M** (mix) |
| D4 | Episode context: `(scores, mano)` sampled from real pre-hand states of Threshold-vs-Threshold matches; no pico states |
| D5 | Reward: `(mine - theirs) / 15`, clipped to +-1 |
| D6 | **20M steps per arm kept** (Phase 0 throughput clears the halving rule); fixed points 5M/10M/20M |
| D7 | BC trains the full actor plus value head; PPO lr 1e-4 |
| D8 | Aux heads off, MC rollouts off, constant `ent_coef` 0.01 |
| D9 | Final evaluation deterministic, full `TrucoMatch` default rules |
| (a) | **H3 is demoted to descriptive** under the pre-registered saturation rule (Threshold vs Random = 87.5 % [86.5, 88.5], n=4000). vs-Random numbers are reported, not tested, and not in the BH family. H2 stays primary |
| (b) | **Arm layout:** M and C run **concurrently, 8 envs each** (rollout batch 4096), identical in both arms |

## Hypotheses

- **H0 (BC, the only hard stop):** validation accuracy >= 70 % on held-out *games*. The clone vs Threshold
  at n=4000 is reported; a soft flag is raised outside [45 %, 55 %]. If H0 fails, stop and report.
- **H1 (learns):** M-final vs Threshold has a Wilson lower bound > 50 %.
- **H2 (generalises; primary):** M-final beats C-final vs **VonNeumann** (held out of training for both arms), p_BH < 0.05.
- **H3 (descriptive only, owner decision (a)):** M and C vs Random are reported with Wilson CIs next to the
  re-measured Threshold-vs-Random baseline (87.5 %). No test, not in the BH family, and no verdict depends on it.

## Config

Fixed now; any difference at run time is a deviation and is listed under "Deviations".

- Code: `training/run.py` (`python -m training.run`), `scripts/pretrain_bc.py`, `scripts/rebench_009.sh`; main at 8acd35f or later.
- **PPO (both arms):** `--n-envs 8` (rollout batch 8 x 512 = 4096), minibatch 2048, 4 epochs, gamma 0.99, GAE 0.95,
  clip 0.2, lr 1e-4, `ent_coef` 0.01, seed 42, `--steps 20000000`, `--checkpoint-every 250000`,
  `--snapshot-every 1000000`, `--eval-every 250000`, `--eval-n 200`, `--inference cpu`, `--reward diff`
  (scale 15), `--context-bank` = the same bank for both arms, both initialised from the same `bc_init.zip`.
  - Arm **M:** default `--opponent-mix thr=0.4,rand=0.2,self=0.4`, `--partners snapshot`.
  - Arm **C:** `--opponent-mix thr=1.0,rand=0.0,self=0.0`, `--partners snapshot`.
- **Context bank:** 20,000 Threshold-vs-Threshold matches, seed 1 (`training.context_bank.build_bank`).
- **BC:** `python -m scripts.pretrain_bc --games 50000 --context-bank <bank> --dataset <npz> --out bc_init.zip --min-val-acc 0.70`
  (validation = games with `game_id % 10 == 0`; best epoch by validation loss).
- **Fixed points** are the first checkpoint at or after 5M / 10M / 20M steps (chunk boundaries overshoot by
  less than one 4096-step rollout; `rebench_009.sh` resolves them by glob).
- Chunked and resumable: `touch <run>/STOP` or SIGTERM stops cleanly (exit 0); `--resume` continues from the saved
  step. The laptop runs by day only, so each night's stop and next-day resume is expected; every resume is
  listed under "Deviations". A resume replays the opponent draws (pool RNG is reseeded per rank); harmless.
- In-loop eval (alarm only; never used to select a checkpoint, gamekit#009): n=200 matches vs Threshold and Random.
- Freeze detector (gamekit#011) ends an arm and is reported as a result.
- **Finals:** n=4000, seat-rotated (`run_arm` + `rotate`), single seed 20261002, deterministic RL, Wilson CIs.
- Statistics: two-proportion tests, BH at q=0.05 over the tested family {H2, the M-vs-C difference vs Threshold
  for non-inferiority, the M-trend pairs}; non-inferiority uses the 95 % CI lower bound of the difference.

## Jobs (`scripts/rebench_009.sh`, n=4000 each)

Baselines: Threshold vs Random, Threshold vs VonNeumann. M-final and C-final vs Threshold / VonNeumann / Random.
bc_init vs Threshold / VonNeumann / Random. M at 5M and 10M vs Threshold and Random (trend).

## Verdict ladder (first match wins)

1. **Collapsed:** the detector fired in either arm (named; its last pre-fire fixed checkpoint is still reported).
2. **Generalises:** H2 holds and the lower bound of (M - C) vs Threshold is > -5 pp.
3. **Generalises with trade-off:** H2 holds, non-inferiority fails.
4. **Control better:** C beats M vs VonNeumann (p_BH < 0.05).
5. **Inconclusive:** anything else.

The former "Breadth only" rung depended on H3 and is removed. Trend within M: fixed points only, pairwise,
BH-corrected.

## Phase 0 (smoke and throughput; not results)

Main at 2748a63, 200k-step runs from a fresh-init net, learner `device=auto`, CPU inference server, laptop
(20 cores) idle, GPU idle.

| config | fps |
|---|---|
| M (mixed pool), 16 envs | 1138 (1124 on a repeat) |
| M, 8 envs | 809 |
| C (Threshold-only), 16 envs | 1691 |
| C, 8 envs | 1036 |
| **M and C concurrent, 8 envs each** | **M 722, C 1211** (combined 1933) |

- Peak RSS about 1.9 GB per run (the concurrent pair summed about 9.2 GB, double-counting shared pages).
- In-loop eval costs about 1 s per 40 matches.
- Inference mode (micro-benchmark, idle GPU, env-steps/s at 8 / 16 envs): local 1343 / 1377, cpu server 893 / 1570,
  cuda server 605 / 1026. Default `cpu`. (With another process holding the GPU at 97 % the cuda server managed 55.)
- **D6 = 20M kept.** Concurrent layout: C reaches 20M in about 4.6 h; M has about 12M by then and finishes alone in
  about 2 h more, so about 6.6 h of laptop wall time in total, roughly one workday. Estimated from a fresh-init
  net; the first real chunks confirm it.
- Checks passed: the pool holds only the run's own snapshots; episode role fractions came out 0.40 / 0.20 / 0.40
  (threshold / self / random: 0.400 / 0.401 / 0.199); SIGTERM saved a checkpoint and exited 0, and `--resume`
  continued from 69,536 to 208,800 steps.
- **Exit-134 fix (#28, 8acd35f):** 5 of 8 smoke runs aborted at interpreter exit
  (`terminate called without an active exception`) after `run.json` was written, because
  `InferenceServer.stop()` did not join its daemon thread. Fixed; 5 consecutive runs then exited 0.
- **Saturation check:** Threshold vs Random on the rebuilt engine = **87.5 % [86.5, 88.5]** (n=4000, seed 20261002),
  outside the pre-registered [15 %, 85 %] band. This triggered decision (a).

### VonNeumann cost (H2 depends on it)

Single laptop core, 20 rollouts per action, n=100: VN vs Threshold 3.52 matches/s; RL (200k-step control
checkpoint) vs VN 4.34 matches/s. Four n=4000 VN jobs (M, C, bc_init vs VN, plus the Threshold-vs-VN
baseline) cost about 3,900 core-seconds: about 15-19 min per job on one laptop core.

- **Route 1 (first choice): the laptop, after PPO finishes**, about 10 min with 8 workers.
- **Route 2 (fallback): the HP**, at an assumed 3.5x slower per core (the orchestrator's figure, not measured by me)
  with 3 workers at nice 19: about 4.5 h for the VN jobs, about 4.7 h for all jobs, one night.
- n=4000 and 20 rollouts are kept. The VN timing used a weak RL policy; a stronger one may play longer matches.

## Limitations (declared now)

One seed per arm; no BC-vs-cold-start ablation; VonNeumann is a single held-out opponent; the engine still
carries simplifications #21-#23; D4 excludes pico a pico contexts; vs-Random is descriptive only (saturated).

## Environment differences (disclosure)

- **Stack:** bringing in gamekit `76c364b` (run-scoped `OpponentPool`, `league`) forced the stack forward:
  gamekit >= 0.3 needs gymnasium >= 1.3, which needs stable-baselines3 >= 2.9, which needs torch >= 2.8.
  The lock moved from torch 2.5.1+cu121 / SB3 2.x to **torch 2.11.0+cu128, SB3 and sb3-contrib 2.9.0,
  gymnasium 1.3.0**. The 111 baseline tests passed on the new stack before any 009 code was added.
- **HP (Phase 4 fallback only):** the HP is CPU-only with 6.6 GB RAM, so it gets a **CPU torch** install instead of
  the locked cu128 wheels. This is an environment difference from the laptop (the catan runs verified identical
  results despite CPU kernels, but that is not assumed here: one n=200 job is re-run on both machines first and
  compared before any HP final counts).

## Deviations

None yet. Each resume, restart, or change from the Config section is listed here with its date.

## Result / Verdict

Not yet run.
