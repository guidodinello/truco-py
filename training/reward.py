"""
Reward functions for the Truco RL environment.

SparseReward (default):
    +1.0 / -1.0 based on whether the training agent's team won the hand.

ShapedReward:
    Sparse reward + small bonuses for winning envido, flor, and tricks.
    Shaping weight is annealed to 0 after a specified number of steps.

MCPotentialReward:
    Sparse reward + V_MC-based terminal adjustment that amplifies surprising
    outcomes. Requires MC rollouts to be enabled in TrucoEnv (mc_rollouts > 0).
    Falls back to pure sparse reward when V_MC is not available (v_mc=0.5).
"""

from engine.game_state import GameState, team_of


class RewardShaper:
    """Base class for reward functions."""

    def compute(self, state: GameState, player_idx: int, done: bool) -> float:  # noqa: ARG002
        raise NotImplementedError

    def on_episode_start(self, _state: GameState, _v_mc: float) -> None:
        """Called at the start of each episode with the MC value estimate.

        Override to implement V_MC-based shaping. Default: no-op.
        `v_mc` is in [0, 1]: probability that the training agent's team wins
        this hand under random play from the initial deal.
        """


class SparseReward(RewardShaper):
    """±1 on hand completion, 0 otherwise."""

    def compute(self, state: GameState, player_idx: int, done: bool) -> float:
        if not done:
            return 0.0
        my_team = team_of(player_idx)
        opp_team = 1 - my_team
        if state.hand_pts[my_team] > state.hand_pts[opp_team]:
            return 1.0
        if state.hand_pts[opp_team] > state.hand_pts[my_team]:
            return -1.0
        return 0.0


class ShapedReward(RewardShaper):
    """
    Sparse ±1 plus intermediate bonuses for sub-game wins.
    The shaping weight decays linearly to 0 over `anneal_steps` steps.
    """

    def __init__(self, anneal_steps: int = 5_000_000, shaping_scale: float = 0.1):
        self._anneal_steps = anneal_steps
        self._shaping_scale = shaping_scale
        self._step = 0
        self._sparse = SparseReward()

        # Track last-known hand_pts to compute deltas
        self._last_hand_pts = [0, 0]

    def compute(self, state: GameState, player_idx: int, done: bool) -> float:
        self._step += 1
        weight = max(0.0, 1.0 - self._step / self._anneal_steps) * self._shaping_scale

        my_team = team_of(player_idx)
        opp_team = 1 - my_team

        # Delta pts since last call (captures flor/envido/trick wins mid-hand)
        delta_mine = state.hand_pts[my_team] - self._last_hand_pts[my_team]
        delta_opp = state.hand_pts[opp_team] - self._last_hand_pts[opp_team]
        self._last_hand_pts = list(state.hand_pts)

        shaping = weight * (delta_mine - delta_opp)

        if done:
            self._last_hand_pts = [0, 0]
            return self._sparse.compute(state, player_idx, done) + shaping

        return shaping

    def reset_step_count(self) -> None:
        self._step = 0


class MCPotentialReward(RewardShaper):
    """
    Sparse ±1 reward with a V_MC-based terminal adjustment.

    V_MC is the win probability estimated from random rollouts at episode start
    (set via on_episode_start). The adjustment amplifies surprising outcomes:

      r = r_sparse - (2*V_MC - 1) * weight

    Where (2*V_MC - 1) maps [0,1] → [-1, +1]:
      - V_MC=0.8 (strong hand): win gives 1 - 0.6*w = 0.4w (expected, less reward)
                                 loss gives -1 - 0.6*w = -1.6w (unexpected, bigger penalty)
      - V_MC=0.2 (weak hand):   win gives 1 + 0.6*w = 1.6w (unexpected, bigger reward)
                                 loss gives -1 + 0.6*w = -0.4w (expected, smaller penalty)

    When mc_rollouts=0 in TrucoEnv, on_episode_start receives v_mc=0.5 and the
    adjustment is zero — this class behaves identically to SparseReward.
    """

    def __init__(self, anneal_steps: int = 5_000_000, shaping_scale: float = 0.3):
        self._anneal_steps = anneal_steps
        self._shaping_scale = shaping_scale
        self._step = 0
        self._sparse = SparseReward()
        self._phi_s0 = 0.0  # 2*v_mc - 1, set each episode

    def on_episode_start(self, _state: GameState, v_mc: float) -> None:  # noqa: ARG002
        self._phi_s0 = 2.0 * v_mc - 1.0

    def compute(self, state: GameState, player_idx: int, done: bool) -> float:
        if not done:
            return 0.0
        self._step += 1
        weight = max(0.0, 1.0 - self._step / self._anneal_steps) * self._shaping_scale
        r_sparse = self._sparse.compute(state, player_idx, done)
        return r_sparse - self._phi_s0 * weight

    def reset_step_count(self) -> None:
        self._step = 0
