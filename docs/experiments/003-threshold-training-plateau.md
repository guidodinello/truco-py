# Phase 1/4 threshold training to 5M steps, and the ~84% plateau

**Date:** 2026-04-12 (training run) / 2026-06-05, 2026-06-06 (triage that found
the plateau)
**Note:** [gamekit#009 — Longer runs / resume when the curve has not bent](https://github.com/guidodinello/gamekit/blob/main/docs/research/009-longer-runs-and-resume.md)

## Config

`uv run training/train.py --opponents threshold --steps 5000000` with aux heads
on (`--aux-heads`, λ_max=0.100, anneal over 10,000,000 steps), MC rollouts=10
(`V_MC` in `obs[169]`), shaped reward off, loaded from
`checkpoints/truco_threshold_final.zip` (`logs/train.log:1-12`). This is the
"Fase 4" run in `README.md`'s pipeline diagram (`README.md:107-124`).

## Environment

No commit — run predates `e70dd16` (this repo's initial commit, 2026-06-04).

## Result

Final training iteration, `logs/train_threshold_5M.log` (tail): `ep_rew_mean
0.3`, `ep_len_mean 2.81`, `explained_variance 0.466`, `approx_kl 0.002644206`,
`clip_fraction 0.0176`, `entropy_loss -0.208`, `total_timesteps 5,079,040`,
completed in **23.4 min**. This is the exact source of `README.md:127`'s
Fase-4 row ("5M | 0.30 | 0.466 | 23 min") — that row is correctly sourced.

Both `approx_kl` and `clip_fraction` stayed within the README's stated healthy
range throughout this run (`README.md:199-200`: `approx_kl < 0.05`,
`clip_fraction < 0.1`); the maximum observed values in this log are
`approx_kl` 0.0033362852 and `clip_fraction` 0.0231. This matters for
[log 005](005-june-threshold-mix-collapse.md): these two metrics never flagged
either self-play collapse in this repo — only `entropy_loss` and `ep_len_mean`
did.

**The plateau claim**, `docs/session-2026-06-06.md:11-17`:

| Checkpoint | vs Threshold (n) |
|---|---|
| `truco_threshold_2000000.zip` | 84.0% (n=150) |
| `truco_threshold_5000000.zip` | ~84% (n=50) |

> Key finding: Threshold training plateaued at ~84% between 2M and 5M steps.

Wilson intervals (`gamekit.mc.wilson_interval`, verified against the package's
own pinned test vector `wilson_interval(50,100) → [0.404, 0.596]`):
- 84.0%, n=150 → **[77.3%, 89.0%]**
- ~84%, n=50 → **[71.5%, 91.7%]**

**The n=50 interval spans 71.5%–91.7%, which contains the repo's stated 90%
goal** (`docs/session-2026-06-05.md:64,83`; `docs/pro-agent-roadmap.md:1`). At
that sample size, "plateau confirmed, 90% is out of reach" is not a supportable
conclusion — the data cannot distinguish a true plateau from a checkpoint that
would have crossed 90% with a larger benchmark.

A sibling figure for the same 2M checkpoint appears in
`docs/session-2026-06-05.md:57` as **85.3%**, with the 06-06 note itself
attributing the 84.0%/85.3% gap to "a different seed" (`session-2026-06-06.md:13`).
`n` for the 85.3% run is not recorded in source.

**Phase 6 ("MC-enhanced") was never run as a distinct phase.** `README.md:128`'s
row (`Fase 6 | truco_threshold_final.zip | +5M | — | — | 42 min`) reuses the
same 2026-04-12 aux-heads/MC-rollout run described above — there is no separate
training invocation, log, or checkpoint for a phase that continues Fase 4 with
additional MC-derived supervision, despite `README.md:117-120` describing Fase 6
as a distinct step "(próximo paso)". The 42-minute figure does not correspond to
any completed-run line in `logs/train.log`.

## Verdict

**gamekit#009 (longer runs when the curve hasn't bent):** inconclusive — and
this is exactly the open question gamekit#009 records. The 2M→5M comparison
that grounds "more threshold training will not push past 84%" rests on an
n=50 benchmark whose 95% interval cannot exclude 90%. Whether the threshold
curve had genuinely bent by 5M steps, or whether it was still climbing and
under-measured, is not resolved by the evidence in this repo.
