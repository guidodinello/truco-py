# Retraining on the fixed engine: BC warm start + PPO against a mixed opponent pool

**Status:** DRAFT. The code for this experiment is in review; the pre-registration is finalised
and committed (with Phase 0 throughput numbers) **before any measured run**. No measured run has
started, and every "Result" section below is empty on purpose.
**Date:** 2026-10-02 (owner decisions D1-D9 recorded)
**Notes:** gamekit#001 (opponent mix), #002 (BC fine-tune lr), #009 (fixed-point trend, resume),
#011 (collapse detection), #013 (run-scoped pool), #022 (team-consistent opponents)

## Motivation

[Log 008](008-seat-rotated-rebenchmarks.md): threshold-trained agents beat Threshold 80.1 % [78.8, 81.3]
but Random only 53.7 % [52.2, 55.2], against a Threshold-vs-Random baseline of 52.2 % (n=4000).
That is exploitation of one opponent, not general play. All pre-#26 numbers describe a different game
(65 actions, old checkpoints refused), so everything is retrained.

## Owner decisions (Guido, 2026-10-02)

| | Decision |
|---|---|
| D1 | Opponent *team* per episode: Threshold 0.4 / Random 0.2 / own snapshot 0.4 (uniform over the run's pool); snapshot every 1M steps |
| D2 | Partner seats: the latest own snapshot (BC init before the first one) |
| D3 | Control arm **C**: Threshold-only opponent team, otherwise identical to arm **M** (mix) |
| D4 | Episode context: `(scores, mano)` sampled from real pre-hand states of Threshold-vs-Threshold matches; no pico states |
| D5 | Reward: `(mine - theirs) / 15`, clipped to +-1 |
| D6 | 20M steps per arm, fixed points 5M/10M/20M; halved (10M; 2.5/5/10M) if Phase 0 throughput is too low |
| D7 | BC trains the full actor plus value head; PPO lr 1e-4 |
| D8 | Aux heads off, MC rollouts off, constant `ent_coef` 0.01 |
| D9 | Final evaluation deterministic, full `TrucoMatch` default rules |

## Hypotheses

- **H0 (BC, the only hard stop):** validation accuracy >= 70 % on held-out *games*. The clone vs Threshold
  at n=4000 is reported; a soft flag is raised outside [45 %, 55 %].
- **H1 (learns):** M-final vs Threshold has a Wilson lower bound > 50 %.
- **H2 (generalises; primary):** M-final beats C-final vs **VonNeumann** (held out of training for both arms), p_BH < 0.05.
- **H3 (breadth):** M-final beats C-final vs Random (p_BH < 0.05), and M-final vs Random exceeds the *re-measured*
  Threshold-vs-Random baseline (p_BH < 0.05).

## Config

- Code: `training/run.py` (`python -m training.run`), `scripts/pretrain_bc.py`, `scripts/rebench_009.sh`.
- PPO: `n_steps` 512, batch 2048, 4 epochs, gamma 0.99, GAE 0.95, clip 0.2, 16 envs, seed 42, one seed per arm.
- Chunked and resumable: checkpoint every 250k steps; `touch <run>/STOP` or SIGTERM stops cleanly; `--resume` continues.
- In-loop eval (alarm only, never used to select a checkpoint, gamekit#009): n=200 matches vs Threshold and Random every 250k steps.
- Freeze detector (gamekit#011) ends an arm and is reported as a result.
- Finals: n=4000, seat-rotated (`run_arm` + `rotate`), single seed 20261002, Wilson CIs.
- Statistics: two-proportion tests, BH at q=0.05 across the family; non-inferiority uses the 95 % CI lower bound of the difference.

## Verdict ladder (first match wins)

1. **Collapsed:** the detector fired in either arm (named; its last pre-fire fixed checkpoint is still reported).
2. **Generalises:** H2 holds and the lower bound of (M - C) vs Threshold is > -5 pp.
3. **Generalises with trade-off:** H2 holds, non-inferiority fails.
4. **Breadth only:** H2 fails and H3 holds.
5. **Control better:** C beats M vs VonNeumann (p_BH < 0.05).
6. **Inconclusive:** anything else.

Trend within M: fixed points only, pairwise, BH-corrected.

## Limitations (declared now)

One seed per arm; no BC-vs-cold-start ablation; VonNeumann is a single held-out opponent;
the engine still carries simplifications #21-#23; D4 excludes pico a pico contexts.

## Environment change (disclosure)

Bringing in gamekit `76c364b` (run-scoped `OpponentPool`, `league`) forced the stack forward:
gamekit >= 0.3 needs gymnasium >= 1.3, which needs stable-baselines3 >= 2.9, which needs torch >= 2.8.
The lock moves from torch 2.5.1+cu121 / SB3 2.x to **torch 2.11.0+cu128, SB3 and sb3-contrib 2.9.0,
gymnasium 1.3.0**. The 111 baseline tests passed on the new stack before any 009 code was added.

## Result / Verdict

Not yet run.
