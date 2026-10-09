# Pro Agent Roadmap — reaching 90%+ win rate

> **Tracking lives in the pinned [Roadmap issue #46](https://github.com/guidodinello/truco-py/issues/46)** (ordering, status, open work).
> This file is the design rationale: the original June options analysis plus Option 4. Current numbers are in the
> experiment logs ([log 009](experiments/009-retrain-mixed-pool.md), [log 010](experiments/010-league-009-checkpoints.md));
> numbers from before #26 describe a different game.

---

## Option 1 — Better rollout policy (easy, ~75-80%)

> Tracked in #42 (as a separate variant: `OmniscientVonNeumannAgent` is the held-out opponent of logs 009–011; the fair one is `DeterminizedVonNeumannAgent`).

**Effort:** ~2h, ~5 lines of code.

The omniscient VonNeumann's EV estimates are calibrated against random opponents. Swap the internal
rollout agents from `RandomAgent` to `ThresholdAgent` so rollouts reflect how a real
opponent actually plays.

In `agents/von_neumann_agent.py`, change `__init__`:

```python
# Before
self._rollout_agents = [
    _SimpleRandom(seed=(seed + i) if seed is not None else None) for i in range(6)
]

# After
from agents.threshold_agent import ThresholdAgent as _Threshold
self._rollout_agents = [
    _Threshold(seed=(seed + i) if seed is not None else None) for i in range(6)
]
```

`ThresholdAgent` is deterministic-ish and fast enough for rollouts. EV estimates will be
more accurate against any opponent that plays better than random.

**Expected gain:** ~5-10pp win rate improvement, minimal speed cost since ThresholdAgent
is rule-based (no rollouts of its own).

---

## Option 2 — Train the existing RL pipeline (medium, ~80-90%)

> Done, via `training/run.py` rather than the `train.py` commands below ([log 009](experiments/009-retrain-mixed-pool.md)): BC warm start, then PPO against a mixed pool. The Phase 2 self-play step is superseded by Option 4.

**Effort:** compute time (~hours on GPU), no new code needed.

The PPO + self-play infrastructure already exists in `training/`. A well-converged
self-play agent learns to exploit specific weaknesses rather than averaging over rollouts.

```bash
# Phase 1 — warm-start against Threshold
uv run training/train.py --opponents threshold --steps 5_000_000

# Phase 2 — self-play against a rolling checkpoint pool
uv run training/train.py --opponents selfplay --steps 50_000_000
```

Key levers:
- `--n-envs 8` — parallel envs, speeds up wall-clock training significantly
- `--shaped-reward` — auxiliary reward signal for envido/flor/truco outcomes mid-hand
- `--load-checkpoint` — resume from a Phase 1 checkpoint into Phase 2

The trained policy is a `MaskablePPO` model (stable-baselines3) with a custom
`TrucoActorCriticPolicy`. Load and benchmark it via the existing `benchmark.py` once
a `RLAgent` wrapper is added to `agents/`.

**Expected ceiling:** 85-90% vs Threshold, depending on training length and self-play
diversity.

---

## Option 3 — CFR / DeepCFR (hard, theoretically optimal)

> Tracked in #45 (scoping only).

**Effort:** weeks, requires building the game tree or a neural network approximation.

Counterfactual Regret Minimization is the gold standard for imperfect-information games
(it's how poker was solved). It converges to a Nash equilibrium — no opponent can
exploit it in expectation.

Two variants:
- **Vanilla CFR** — tabular, requires enumerating the full information-set tree.
  Truco's tree is large but manageable with abstraction (bucket card strengths, round-trip
  the bidding ladder).
- **DeepCFR** — neural network approximates the regret table. Scales to large games,
  used in Libratus/Pluribus.

This is only worth pursuing if the goal is a *provably unexploitable* agent rather than
just a strong one. For research/competition purposes, Option 2 gets you most of the way
there at a fraction of the complexity.

---

## Recommended path

> Historical (June). The current ordering is the Now / Next / Later list in #46.

1. **Start with Option 1** — quick win, validates that better rollout opponents help.
   Benchmark the result; if win rate jumps to 75%+, the EV-estimation hypothesis is confirmed.

2. **Run Option 2 training** — the pipeline exists, just needs compute time.
   Target: 50M self-play steps. Checkpoint every 5M and benchmark against Threshold to
   track progress.

3. **Revisit CFR** only if self-play plateaus below 90% and you need a Nash-optimal strategy.

---

## Option 4 — League-based self-play (planned, gated)

Naive self-play did not carry over to a different-style opponent: in [log 009](experiments/009-retrain-mixed-pool.md) the arm with
self-snapshot and Random opponents (M) lost to the Threshold-only arm (C) against held-out VonNeumann, 56.8% vs 64.1%, one seed,
yet beat C head to head in [log 010](experiments/010-league-009-checkpoints.md) (M20 beats C20 58.9%). M changed the self share and
the Random share together and both arms used snapshot partners, so the cause is untested. Truco is imperfect-information and
team-based, and the partner is also learned.

Proposal: league / prioritized fictitious self-play. Sample opponents from past snapshots plus fixed baselines, weighted by win rate
against the learner, baselines always kept, judged only on held-out opponents (VonNeumann). The method and the possible gamekit
support (a sampler driven by `gamekit.league`, [gamekit#39](https://github.com/guidodinello/gamekit/issues/39)) live in
[gamekit note 023](https://github.com/guidodinello/gamekit/blob/main/docs/research/023-league-selfplay.md).

Tracked in #44. Gated on the gamekit note 001 ablation (#43) and [exp 011](experiments/011-league-vonneumann.md) (#41).
