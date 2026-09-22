# Self-play `--threshold-mix 0.5` run and its collapse

**Date:** 2026-06-06
**Note:** [gamekit#001 — Self-play opponent mix vs a fixed baseline](https://github.com/guidodinello/gamekit/blob/main/docs/research/001-self-play-opponent-mix.md), [gamekit#010 — Entropy schedule instead of a fixed coefficient](https://github.com/guidodinello/gamekit/blob/main/docs/research/010-entropy-schedule.md), [gamekit#011 — KL guard vs the previous snapshot](https://github.com/guidodinello/gamekit/blob/main/docs/research/011-kl-guard.md)

## Config

`uv run training/train.py --opponents selfplay --steps 20000000 --n-envs 16
--shaped-reward --threshold-mix 0.5 --load checkpoints/truco_threshold_5000000.zip`
— header confirmed at `logs/train.log:209-220`: selfplay mode, 20,000,000 target
steps, 16 envs, shaped reward on, aux heads off, `Threshold mix : 0.50
(selfplay only)`, GPU inference server active (`Device: cuda`). This is the
"Phase 2" run in `docs/session-2026-06-06.md:29-50` (started ~13:52, resumed
from a 5.5M checkpoint at 14:31, restarted again at 16:12 after saving
`truco_selfplay_final.zip`). The `--threshold-mix` CLI flag was added in this
session (`docs/session-2026-06-06.md:67`) and is wired to gamekit's
`OpponentPool(..., baseline_mix=threshold_mix)` (`training/env.py:158`) — the
brief's "`baseline_mix`" is the internal kwarg name, not the CLI flag.

Rationale for 0.5 over the default 0.2, `docs/session-2026-06-06.md:35`:
> Why 0.5? Prior selfplay run used default 0.2 (80% self-play, 20% Threshold)
> and collapsed to 56%. 0.5 keeps a strong Threshold anchor while still building
> self-play diversity.

## Environment

No commit — this run was never committed; it predates `e70dd16` by nothing
(same day range as the repo's active development, 2026-06-06) but there is no
commit hash to cite for the training invocation itself.

## Result

Collapse trace, `docs/session-2026-06-06.md:107-118`, verbatim:

| Step | entropy_loss | ep_rew_mean | ep_len_mean | FPS |
|---|---|---|---|---|
| 5.6M (start) | -0.14 | ~0.4 | ~2 | 1440 |
| 6.47M | -0.027 | 0.197 | ~2 | 1330 |
| 6.6M+ | ~0 | -7.28 | 165 | 711 |

Confirmed directly against the raw PPO log, `logs/train_selfplay_gpu.log`
(extracted `total_timesteps, ep_len_mean, ep_rew_mean, entropy_loss,
explained_variance`):

```
5709824  1.97   0.297    -0.14      0.398
6119424  1.85   0.606    -0.189     0.364   ← entropy still healthy
6250496  2.51   0.531    -0.117     0.472   ← entropy starts collapsing
6455296  108    0.286    -0.0131    0.808   ← first episode-length blowup
6742016  6.66  -0.0871   -3.1e-05   0.961   ← entropy effectively zero
6889472  165   -6.18     -1.18e-05  0.961   ← final logged iteration
```

Final logged iteration (`logs/train_selfplay_gpu.log`, last block): `ep_len_mean
165`, `ep_rew_mean -6.18`, `fps 711`, `total_timesteps 6,889,472`, **`approx_kl
0.0`**, **`clip_fraction 0`**, `entropy_loss -1.18e-05`, `explained_variance
0.961`, `n_updates 3360`. Training was killed at ~6.6M of the planned 20M steps
(`docs/session-2026-06-06.md:118`). Checkpoints `truco_selfplay_6100000.zip` and
`truco_selfplay_6600000.zip` were saved but never benchmarked.

**The collapse signature is `approx_kl → 0.0` and `clip_fraction → 0` — a
frozen, deterministic policy — not a KL spike.** This is the opposite of what a
guard tuned to catch "policy changed too fast" would trigger on.

**`ep_rew_mean = -7.28`/`-6.18` breaks the documented win-rate-proxy formula.**
`README.md:196` defines `ep_rew_mean` as "Win rate proxy: `(1 + valor) / 2`",
which requires per-episode reward in `[-1, 1]`. This run used `--shaped-reward`;
`training/reward.py:65-83`'s `ShapedReward.compute` returns
`sparse + weight * (delta_mine - delta_opp)` **per step**, so a 165-step episode
accumulates far outside `[-1, 1]`. The proxy formula is stale for every shaped
run, including this one and the April run in [log 004](004-april-selfplay-collapse.md).

**Root cause: hypothesised in-repo, confirmed upstream, not yet adopted here.**
`docs/session-2026-06-06.md:120`:
> With `threshold_mix=0.5`, the 50% checkpoint opponents all use the SAME latest
> checkpoint (as picked up by the glob).

gamekit PR #24 ("run-scope `OpponentPool`'s checkpoint pool", merged
2026-09-20T19:45:45Z) confirms a related but distinct mechanism, naming
truco-py explicitly in its description: because `OpponentPool` samples uniformly
over every file matching `truco_selfplay_*.zip` in a shared `checkpoints/`
directory, a **stale, already-collapsed** checkpoint from an earlier run (e.g.
the April `truco_selfplay_final.zip`) stays in the sample pool for every later
run and contaminates it, in proportion to how many stale files are lying
around — this does not wash out with more training.

**truco-py has not adopted the fix.** `training/env.py:151-159` constructs
`OpponentPool(selfplay_dir, "truco_selfplay_*.zip", ..., baseline_mix=
threshold_mix)` with no `run_id=` argument, and `uv.lock` pins `gamekit` at
0.2.0 — the version that added `run_id`-scoped pools is later. The
contamination this run exhibited is still possible with the current code.

## Verdict

**gamekit#001 (self-play opponent mix):** inconclusive, confounded by pool
contamination — same reasoning as [log 004](004-april-selfplay-collapse.md).
Raising the mix from 0.2 to 0.5 did not prevent collapse, but the confirmed
upstream root cause (stale checkpoints contaminating the glob, gamekit#24) means
this run does not isolate the mix ratio as the variable under test. This is not
evidence that a heavier baseline share doesn't help — it's evidence that
something else was already broken.

**gamekit#010 (entropy schedule):** untested. The session's own next-steps list
(`docs/session-2026-06-06.md:` "Option C") proposed raising `ent_coef` from 0.01
to 0.05–0.1 and required a new `--ent-coef` CLI flag; that flag was never built
and no entropy-schedule run exists in this repo.

**gamekit#011 (KL guard):** supports the note, with a caveat the note itself
needs to carry. A guard watching for `approx_kl` to *rise* above a threshold
would not have caught this collapse — `approx_kl` and `clip_fraction` both went
to (or stayed near) zero while the policy froze. `entropy_loss` and
`ep_len_mean` are the metrics that actually moved. Any KL-guard implementation
built from gamekit#011 needs to watch for a collapse-to-zero on
`approx_kl`/`clip_fraction` co-occurring with entropy collapse, not only a
spike.
