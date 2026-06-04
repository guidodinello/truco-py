# Plan: Truco Uruguayo RL Agent

## Session

claude --resume "truco-rl-agent-plan"  

## Context

The existing project (`truco-py`) is a Monte Carlo simulation that derives optimal thresholds for envido and flor decisions. The goal is to extend it into a full playing bot using Reinforcement Learning, organized within the same repo in new subfolders.

The core insight driving the architecture: **MC and RL are complementary, not competing**. MC computes optimal thresholds for isolated sub-decisions (envido, flor) very efficiently. RL handles sequential, multi-agent decisions where the optimal move depends on opponent behavior. New MC experiments can be incorporated into an already-trained RL agent incrementally — no need to retrain from scratch.

Hardware: RTX 4050 6GB, i5-13500HX 14-core, 16GB RAM — sufficient for this scale.

---

## Folder Structure

```
truco-py/
├── truco.py                    (existing — DO NOT modify)
├── experimentos/               (existing — DO NOT modify)
│
├── engine/
│   ├── __init__.py
│   ├── card.py                 # card_strength(), TRUCO_ORDER constant
│   ├── game_state.py           # GameState dataclass
│   ├── phases.py               # Phase IntEnum + transitions
│   ├── actions.py              # Action IntEnum (53 total)
│   └── game.py                 # TrucoGame: reset/legal_actions/apply_action/get_rewards
│
├── agents/
│   ├── __init__.py
│   ├── base.py                 # Agent ABC: choose_action(state, legal_actions, player_idx)
│   ├── random_agent.py         # Uniform random from legal_actions
│   └── threshold_agent.py      # MC-derived thresholds hardcoded as policy
│
├── training/
│   ├── __init__.py
│   ├── state_encoder.py        # obs_to_vector(): GameState -> np.ndarray (204-dim)
│   ├── env.py                  # TrucoEnv(gymnasium.Env) + action_masks()
│   ├── reward.py               # RewardShaper: sparse +1/-1, optional shaped bonuses
│   ├── self_play.py            # SelfPlayManager: checkpoint pool
│   └── train.py                # Entry point: MaskablePPO + SubprocVecEnv + --load flag
│
└── scripts/
    ├── benchmark.py            # Win-rate comparison between any two agents
    ├── eval_agent.py           # Load checkpoint, evaluate vs threshold agent
    └── pretrain_bc.py          # Behavioral Cloning pre-trainer (ThresholdAgent -> policy init)
```

---

## What to Reuse from truco.py

All scoring logic is directly importable — do not reimplement:

| Function                             | Used in                                         |
| ------------------------------------ | ----------------------------------------------- |
| `construir_mazo()`                   | `TrucoGame.reset()`                             |
| `simular_mano()`                     | `TrucoGame.reset()` — for deal + muestra        |
| `tiene_flor()`                       | Precomputed once on deal, stored in `GameState` |
| `calcular_flor()`                    | Same                                            |
| `calcular_envido()`                  | Same                                            |
| `es_pieza()`, `valor_envido_carta()` | Used inside scoring                             |
| `EQUIPO_A`, `EQUIPO_B`, constants    | Imported directly                               |

MC thresholds become constants in `threshold_agent.py`:
```python
MC_THRESHOLDS = {
    "envido_1v1": 28, "envido_team": 33,
    "flor_1v1": 35, "flor_1v2_aggressive": 37, "flor_1v2_passive": 38,
}
```

---

## Key Design Decisions

**Action space**: Flat discrete, 53 actions (4 flor + 4 envido + 4 truco + 1 fold + 40 card plays). Heavy masking (~3-5 legal actions at any time). Use `MaskablePPO` — without it, the agent wastes gradient on "don't play cards you don't have."

**State vector (204-dim)**:
- Own 3 cards: 40-dim one-hot
- Played cards (public): 40-dim one-hot
- Current trick cards: 40-dim one-hot
- Phase one-hot: 4-dim
- Bid levels (flor/envido/truco): 3 floats
- Who has flor (public): 6-dim
- Own envido pts, flor pts: 2 floats (normalized)
- Team scores, malas flags: 4 floats
- Trick winners: 18-dim (6 players × 3 tricks)
- Player position + team membership: 12-dim

**Señas**: Excluded from v1. Add in v2 after basic agent works.

**Episode structure**: Single-hand episodes first (30-80 steps). Extend to full multi-hand games (first to 30 pts) once single-hand agent is solid.

**Reward**: Sparse ±1 for win/loss by default. Optional shaped bonuses (envido/flor/trick wins) to speed up early training, annealed to 0 after 5M steps.

**Seat randomization**: At each `reset()`, the training agent is assigned a **random seat** (0-5). The state encoder includes `player_position` (6-dim one-hot) so the network conditions on its role automatically. This avoids biasing the agent toward always playing as mano — it must learn all 6 seats, including pie (last to act), which has a fundamentally different strategy in envido bidding.

---

## MC ↔ RL Integration Strategy

MC experiments and RL training are designed to reinforce each other throughout the project lifecycle — not just at initialization.

### How MC knowledge flows into RL (implemented)

**1. ThresholdAgent as grounded baseline**
`ThresholdAgent` encodes all MC-derived thresholds. It is used as:
- The initial opponent during PPO warm-start (Phase 4)
- A permanent 20% presence in the self-play opponent pool (prevents strategy collapse)
- The source policy for Behavioral Cloning

**2. Behavioral Cloning (BC) — fast policy initialization**
Instead of learning from scratch via PPO, BC pre-trains the policy to imitate ThresholdAgent in ~100k steps:
```
ThresholdAgent plays all 6 seats → collect (obs, action) pairs → cross-entropy loss → init policy weights
```
This achieves in minutes what PPO warm-start takes ~50M steps to accomplish.

```bash
uv run scripts/pretrain_bc.py --games 50000 --epochs 10 --out checkpoints/bc_init.zip
uv run training/train.py --opponents threshold --steps 2000000 --load checkpoints/bc_init.zip
```

**3. Incremental MC → BC updates**
When new MC experiments produce better thresholds (e.g. truco thresholds, score-dependent envido):
1. Update `MC_THRESHOLDS` in `threshold_agent.py`
2. Run BC fine-tuning on the existing checkpoint — no full retraining needed:
```bash
uv run scripts/pretrain_bc.py --games 20000 --epochs 5 \
    --load checkpoints/truco_selfplay_final.zip \
    --out checkpoints/bc_updated.zip
uv run training/train.py --opponents threshold --steps 500000 --load checkpoints/bc_updated.zip
```
The RL agent already knows how to play; BC only updates the specific decisions the new MC results affect.

**4. MC-informed reward shaping**
`ShapedReward` rewards sub-game wins (envido, flor, tricks) to accelerate early learning. The shaping weight anneals to 0 after 5M steps so late-game PPO optimizes for win rate directly.

---

### Advanced MC → RL knowledge injection (planned)

The approaches above use MC knowledge *indirectly* (as behavior to imitate or opponents to play against). The following techniques inject MC knowledge *directly* into the network, forcing it to internalize the exact probabilities our experiments compute. These are complementary — each targets a different part of the learning problem.

---

**5. Auxiliary prediction heads on MC-known quantities**

The core idea: add small output heads to the shared PPO trunk that are supervised on quantities your MC experiments compute exactly. Forcing the network to predict these makes the trunk learn better representations, which benefits the main policy.

This is the approach used in AlphaStar (unit-type predictions) and OpenAI Five (game-state predictions). The supervision signal is very clean because MC gives exact answers, not noisy labels.

Candidate auxiliary heads for Truco:
| Head | Supervision source | MC experiment |
|---|---|---|
| P(my envido ≥ X) | Exact distribution from `calcular_envido()` | `experimento_envido` |
| P(opponent has flor) | Dealt hand distribution conditioned on known cards | `experimento_flor` |
| EV(accept truco bid) | MC rollouts per card-strength combination | future experiment |
| P(my flor wins 1v1) | `experimento_flor_decision_1v1` exact results | `experimento_flor_decision_1v1` |

Training: auxiliary losses are added to the PPO loss with a small weight (λ ≈ 0.1–0.5), annealed to 0 after ~10M steps so late training focuses purely on win rate.

```
L_total = L_PPO + λ_aux * Σ L_auxiliary_i
```

Implementation: add heads after the shared `mlp_extractor` in a custom `ActorCriticPolicy`. Labels are computed from `GameState` fields at each `env.step()` call — no separate data pipeline needed.

---

**6. KL distillation from ThresholdAgent (soft BC)**

BC pre-training (point 2) is hard: the RL agent is forced to copy ThresholdAgent exactly during initialization, then the constraint is dropped entirely. A softer alternative keeps a KL penalty throughout training that decays over time:

```
L_total = L_PPO + λ(t) * KL(π_RL || π_threshold)
```

Where `λ(t)` anneals from ~0.5 to 0 over the first 5M steps.

**Why this is better than hard BC**: the RL agent can deviate from ThresholdAgent when it discovers a strictly better move, but pays a cost for diverging without justification. Hard BC imposes a constraint at init and forgets it; soft KL keeps it as a regularizer throughout early training.

Used in robotics (learning from MPC oracles) and game AI (learning from search policies).

---

**7. MC value bootstrap for the PPO value head**

The value function is usually the bottleneck in PPO — it needs many samples to learn accurate state values, and poor value estimates cause noisy policy gradients. MC rollouts can give a head start.

After each `env.reset()`, run N quick MC rollouts (uniform random play from the dealt state) to estimate V_MC(s_0). Use this as an additional regression target for the value head during early training:

```
L_value = L_PPO_value + λ_v * (V_θ(s) - V_MC(s))²
```

This is exactly what AlphaGo Zero's MCTS does at each tree node — it just calls it "rollout value." The difference here is that V_MC is precomputed offline per deal rather than online per step.

**Practical note**: MC rollouts are cheap (microseconds per game in pure Python). 100 rollouts per reset adds negligible overhead and gives a coarse but unbiased estimate of hand value before any card is played.

---

**8. Potential-based reward shaping from MC values (theoretically clean)**

The existing `ShapedReward` gives ad-hoc bonuses for sub-game wins. A theoretically grounded alternative uses potential-based shaping:

```
r_shaped(s, a, s') = r_sparse(s') + γ * Φ(s') - Φ(s)
```

Where `Φ(s) = V_MC(s)` — the MC-estimated value of state s.

This is provably *policy-invariant*: it cannot change the optimal policy, only the speed of convergence. The ad-hoc shaped reward does not have this guarantee. Replace `ShapedReward` with this formulation once V_MC rollouts are implemented (point 7 above).

---

### Priority and implementation order

| # | Technique | ROI | Complexity | Depends on |
|---|---|---|---|---|
| 5 | Auxiliary heads | High | Medium | MC experiment results (already have) |
| 6 | KL distillation | Medium | Low | ThresholdAgent (already have) |
| 7 | MC value bootstrap | Medium | Low | MC rollout runner |
| 8 | Potential-based shaping | Medium | Low | Point 7 |

Recommended order: **6 → 7+8 → 5**. Points 6–8 are low complexity and can be added to the existing `train.py` / `reward.py` without architectural changes. Point 5 requires a custom `ActorCriticPolicy` subclass.

---

### Future MC experiments worth running

| Experiment                                 | What it unlocks                                      |
| ------------------------------------------ | ---------------------------------------------------- |
| Truco bid/fold thresholds by card strength | Replace heuristic (strength ≥ 8) with MC-optimal; feeds point 5 auxiliary head |
| Score-dependent envido thresholds          | Different thresholds when behind/ahead on game score |
| Multi-flor interactions (3-flor vs 2-flor) | Currently simplified; proper EV per scenario         |
| Señas signaling thresholds                 | Required for v2; MC can define baseline conventions  |

Each new experiment → update ThresholdAgent → short BC pass → stronger RL starting point.

---

## Implementation Phases

### Phase 1: Game Engine ✅
Build `engine/` completely. Validate with:
```
scripts/benchmark.py --mode random --n 10000
```
- 0 exceptions across 10k games = engine is correct
- ~50% win rate each team = scoring is balanced

### Phase 2: Threshold Agent ✅
Build `agents/`. Validate:
```
scripts/benchmark.py --mode threshold_vs_random --n 10000
```
- ThresholdAgent should win 60-70% vs random. Less = engine bug.

### Phase 3: Gym Env + PPO sanity check ✅
Build `training/env.py` + `state_encoder.py`. Validate:
- `env.reset()` / `env.step()` complete without error
- Action masks never empty
- Mean episode reward increases over 100k training steps

### Phase 3.5: Behavioral Cloning pre-training
Pre-train policy to imitate ThresholdAgent before any PPO:
```bash
uv run scripts/pretrain_bc.py --games 50000 --epochs 10 --out checkpoints/bc_init.zip
```
- Goal: BC accuracy ≥ 70% on held-out ThresholdAgent actions
- Takes ~5 minutes; replaces the need for a 5M-step PPO warm-start

### Phase 4: Warm-start RL (PPO fine-tuning from BC)
Fine-tune the BC checkpoint with PPO against ThresholdAgent:
```bash
uv run training/train.py --opponents threshold --steps 2000000 --load checkpoints/bc_init.zip --n-envs 32
```
- Goal: >60% win rate vs ThresholdAgent within 2M steps (faster convergence vs cold-start PPO)
- Watch: `ep_rew_mean` trending up, `explained_variance` toward 1.0

### Phase 5: Self-play
Switch opponents to checkpoint pool. Keep ThresholdAgent at 20% of pool.
```bash
uv run training/train.py --opponents selfplay --steps 50000000 --n-envs 32
```
- Checkpoint every 500k steps (~17 min total at 4900 fps with 32 envs)
- ThresholdAgent presence in pool prevents degenerate strategy collapse

---

## Training Metrics Guide

| Metric               | What it means                     | Healthy trend         |
| -------------------- | --------------------------------- | --------------------- |
| `ep_rew_mean`        | Win rate proxy: `(1 + value) / 2` | ↑ toward ~0.3–0.5     |
| `explained_variance` | Value function quality            | ↑ toward 1.0          |
| `entropy_loss`       | Policy randomness                 | Slowly ↓ in magnitude |
| `approx_kl`          | Policy change per update          | Stay < 0.05           |
| `clip_fraction`      | % of clipped PPO updates          | Stay < 0.1            |

`ep_rew_mean` and `explained_variance` are the primary signals. `loss`/`value_loss` alone are not reliable indicators of playing strength.

---

## Dependencies

```toml
"torch>=2.3",           # GPU: point to pytorch-cu121 index; CPU: pytorch-cpu index
"gymnasium>=0.29",
"stable-baselines3>=2.3",
"sb3-contrib>=2.3",     # MaskablePPO — critical
"numpy>=1.26",
"tensorboard>=2.16",
```

PyTorch index configured in `pyproject.toml` via `[tool.uv.sources]`.
Current setup: `pytorch-cu121` (driver 535.x, CUDA 12.1 compatible).
