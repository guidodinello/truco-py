# `gamekit.rl` adapter parity check

**Date:** 2026-09-20 (PR merged 2026-09-20T14:50:15Z)
**Note:** [gamekit#005 — Eval statistics: Wilson intervals and eval-in-loop](https://github.com/guidodinello/gamekit/blob/main/docs/research/005-eval-statistics.md)

## Config

Not a training run — a regression/parity gate for `guidodinello/truco-py` PR #2
("Adopt gamekit.rl: TrucoEnv becomes a thin adapter over SingleAgentEnv"). Ran
`match_rl_vs_random`/`match_rl_vs_threshold` at `--n 200`, `match_rl_vs_vonneumann`
at `--n 40`, all `--seed 42`, against `checkpoints/truco_threshold_final.zip`,
executed once on the PR branch and once on `main` from a throwaway worktree.

## Environment

Commit `c7caa1c` ("Adopt gamekit.rl: TrucoEnv becomes a thin adapter over
SingleAgentEnv"), truco-py#2, merged into `main` 2026-09-20, **after** the
seat-rotation fix in truco-py#1 ([log 006](006-seat-rotation-deconfound.md)) —
so unlike every session-note figure, these numbers are post-rotation.
`gamekit` bumped to `gamekit[rl]`, resolved against gamekit#15.

## Result

PR #2's parity table, byte-identical on `main` and the branch:

| Mode | Result | n |
|---|---|---|
| `match_rl_vs_random` | RL 104 / Random 96 / Tie 0 | 200 |
| `match_rl_vs_threshold` | RL 158 / Threshold 42 / Tie 0 | 200 |
| `match_rl_vs_vonneumann` | RL 12 / VonNeumann 28 / Tie 0 | 40 |

Wilson intervals (`gamekit.mc.wilson_interval`, formula sanity-checked against
the package's own pinned test vector):
- vs Threshold: **79.0%, n=200 → [72.8%, 84.1%]**
- vs Random: **52.0%, n=200 → [45.1%, 58.8%]**
- vs VonNeumann: **30.0%, n=40 → [18.1%, 45.4%]**

These are **the only post-rotation, reproducible, checkpoint-attributed RL win
rates in this repo.** Every other RL figure (84.0%, 85.3%, 56.0%, 57.3%, 60.6%,
65%, 59%, 53%) is pre-rotation prose from a session note, with no raw win/loss
count and, in most cases, no recorded `n`.

`checkpoints/truco_threshold_final.zip`'s 79.0% [72.8%, 84.1%] vs Threshold does
**not reach the 90% goal** stated in `docs/pro-agent-roadmap.md:1` and
`docs/session-2026-06-05.md:64,83` — and its interval doesn't overlap 90%
either, unlike the ambiguous n=50 figure in
[log 003](003-threshold-training-plateau.md).

## Verdict

**gamekit#005 (Wilson intervals / eval statistics):** does not test this note's
hypothesis — this was a determinism/regression check for a refactor (identical
counts prove the adapter didn't change behavior), not an experiment measuring
whether Wilson intervals or eval-in-loop monitoring improve anything. Linked
here because it's the nearest existing note and because it is, incidentally,
the first and only place in this repo's history where Wilson intervals were
computed on a post-rotation RL benchmark. Recorded for the numbers: this is the
current honest baseline for `truco_threshold_final.zip`'s strength, and it does
not clear the 90% target.
