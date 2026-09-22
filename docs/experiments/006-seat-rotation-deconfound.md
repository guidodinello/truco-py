# Seat-rotation de-confound (truco-py#1)

**Date:** 2026-09-20 (PR merged 2026-09-20T03:12:27Z)
**Note:** [gamekit#005 — Eval statistics: Wilson intervals and eval-in-loop](https://github.com/guidodinello/gamekit/blob/main/docs/research/005-eval-statistics.md)

## Config

No training run — this is a benchmark-methodology fix. `guidodinello/truco-py`
PR #1 replaced `scripts/benchmark.py`'s 11 hardcoded `--mode` branches with a
`MODES` registry over `gamekit.benchmark.run_arm`, and in doing so introduced
seat rotation that truco-py's team-based (2 teams of 3, 6 seats) match play
never had.

## Environment

Commit `722629c` ("Adopt gamekit: Agent protocol, mode-registry benchmark,
mc.wilson_interval"), truco-py#1, merged into `main` 2026-09-20.

## Result

The confound, from PR #1's own description:
> `engine/game.py`'s `current_player=0` always started Team A, and Team A won
> ties — a mano-advantage confound rotation removes.

Confirmed in source: `engine/game.py:79` defaults `current_player=0` at game
construction, and (pre-fix) nothing rotated which team occupied that seat across
matches.

PR #1's benchmark-parity verification, `threshold_vs_random` at `seed=42 n=1000`:
- Rotation pinned to zero (bypassing the seat-occupancy check to reproduce
  `main`'s exact behavior): **476/462/62** (win/loss/tie).
- With production rotation on (the shipped code path): **456/473/71**.

Wilson intervals for Threshold's win share (excluding ties from the denominator
is not how these counts are reported in the PR body, so these are computed
directly over win/(win+loss+tie) = win/1000):
- Pinned-zero (pre-rotation-equivalent): **47.6%, n=1000 → [44.5%, 50.7%]**
- Production (post-rotation): **45.6%, n=1000 → [42.5%, 48.7%]**

**The two intervals overlap heavily.** The de-confounding shift (476→456 wins,
462→473 losses, 62→71 ties) is in the expected direction — Threshold's edge
shrinks once it no longer always gets the mano-advantaged seat — but at n=1000
it is not distinguishable from noise.

**No RL benchmark was re-run after this fix.** truco-py#2 (merged the same day)
did benchmark `truco_threshold_final.zip` post-rotation (see
[log 007](007-gamekit-rl-adapter-parity.md)), but that is the only post-#1 RL
number in the repo. Every win rate recorded before 2026-09-20 — 84.0%, 85.3%,
~84%, 56.0%, 57.3%, plus the ThresholdAgent-vs-Random figures scattered across
`README.md:104` (~65-70%), `docs/session-2026-06-05.md:47` (~48%), and `:55`
(53%) — was measured under the pre-rotation, tie-favors-Team-A rule and is
**not directly comparable** to anything measured afterward.

A related methodology change from the same PR: `scripts/benchmark.py:232-234`
now rejects odd `--n` ("`--n` must be even (2-role lineup, one role per team
slot)"). The n=150 and n=50 triage runs recorded in
`docs/session-2026-06-06.md:11-15` are **not re-runnable as recorded** under the
current script.

## Verdict

**gamekit#005 (Wilson intervals / eval statistics):** inconclusive on its own
terms — this PR adopted `gamekit.mc.wilson_interval` for the MC experiments
(`experimentos/*.py`, `engine/truco.py`) but the seat-rotation fix itself is a
methodology change, not a statistics one, and no post-fix RL win rate was
computed with a large enough `n` to confirm or refute anything using the new
interval method. **No existing gamekit note actually covers "positional/mano
advantage must be rotated out of a benchmark arm"** — gamekit#12 documents the
seat-as-competitor-slot vocabulary mapping this PR relies on, but not the
confound-removal hypothesis itself. Proposed as a new gamekit note candidate in
this PR's description.
