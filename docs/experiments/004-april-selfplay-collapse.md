# April self-play collapse (Phase 2, first occurrence)

**Date:** 2026-04-05/06, per `checkpoints/archive/truco_selfplay_april_collapsed.zip`
and `logs/MaskablePPO_selfplay_*` tfevents timestamps
**Note:** [gamekit#001 — Self-play opponent mix vs a fixed baseline](https://github.com/guidodinello/gamekit/blob/main/docs/research/001-self-play-opponent-mix.md), [gamekit#011 — KL guard vs the previous snapshot](https://github.com/guidodinello/gamekit/blob/main/docs/research/011-kl-guard.md)

## Config

Self-play training with the default opponent mix (`threshold_mix=0.2`, i.e. 20%
ThresholdAgent / 80% checkpoint-pool self-play), loaded from `bc_init.zip`
directly — per `README.md:132`: "`truco_selfplay_final.zip` (apr 6) es de una
corrida que cargó `bc_init.zip` directamente, saltándose la Fase 4." The June-6
run that later hit the same failure (`docs/session-2026-06-06.md:120`)
hypothesizes the mechanism was the checkpoint glob always resolving to the same
latest checkpoint — see [log 005](005-june-threshold-mix-collapse.md) for the
confirmed root cause.

## Environment

No commit — run predates `e70dd16` (this repo's initial commit, 2026-06-04).

## Result

Outcome, `docs/session-2026-06-05.md:59,61-62`:

> | RL selfplay_final | TBD | **57.3%** ✗ |
> **Key finding:** The self-play model REGRESSED vs Threshold (57.3%) compared
> to the 2M threshold model (85.3%). Strategy collapse — it over-optimized
> against its own past versions and lost the edge against rule-based opponents.

A second measurement of the same checkpoint (or a re-run against it), one day
later, `docs/session-2026-06-06.md:15`:

> | `truco_selfplay_final.zip` | **56.0%** (n=150) | Strategy collapse |

Wilson interval for the n=150 figure: **56.0%, n=150 → [48.0%, 63.7%]**. `n` for
the 57.3% figure is not recorded in source.

Compared against the 2M threshold checkpoint's interval from
[log 003](003-threshold-training-plateau.md) — 84.0%, n=150 → [77.3%, 89.0%] —
**the two intervals do not overlap.** The regression from ~84% to ~56% is a real
effect at this sample size, independent of the 84.0%/85.3% ambiguity noted
elsewhere.

**The PPO trace for this specific April run is not directly available.**
`logs/MaskablePPO_selfplay_1` through `_6` (tfevents, dated 2026-04-05/06) exist
but were not parsed for this log — they are binary TensorBoard event files, not
text. The claim that this collapse shares the June run's KL/clip_fraction
signature comes from `docs/session-2026-06-06.md:116`:

> Same pattern as the April collapse (selfplay_final → 56% vs Threshold)

That is the June session author's own comparison, made in-repo; it is not
independently re-derived here from the April tfevents. The confirmed
`approx_kl → 0.0` / `clip_fraction → 0` signature documented in
[log 005](005-june-threshold-mix-collapse.md) is measured from the June run's
plain-text log, not the April one.

## Verdict

**gamekit#001 (self-play opponent mix):** inconclusive, confounded. The
confirmed root cause of the *June* recurrence of this failure (gamekit#24: stale
collapsed checkpoints staying in the sample pool across runs, contaminating the
opponent distribution) was not the mix ratio itself. Since this April run used
the default `threshold_mix=0.2` and collapsed the same way the June 0.5-mix run
later did (see [log 005](005-june-threshold-mix-collapse.md)), the operative
variable across both failures looks like pool contamination, not the specific
mix value. A run where the mix ratio was not the thing that broke is **not a
valid test of "does a heavier baseline share prevent collapse"** — it neither
confirms nor refutes gamekit#001's hypothesis. This is consistent with, and adds
supporting detail to, gamekit#001's own Counter-evidence section, which already
notes that mix ratio "matters less than something actually watching the eval
curve."

**gamekit#011 (KL guard):** inconclusive for this specific run — the KL/
clip_fraction trace is inferred from the June run by analogy, not independently
measured here. See [log 005](005-june-threshold-mix-collapse.md) for the
confirmed measurement this note actually rests on.
