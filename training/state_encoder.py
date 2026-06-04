"""
Encodes a GameState into a fixed-size observation vector for the RL agent.

Vector layout (204 dimensions total):

  [  0: 40] own_cards          — one-hot over 40-card deck (own 3 cards)
  [ 40: 80] played_cards       — one-hot: all cards played so far (public)
  [ 80:120] current_trick      — one-hot: cards in the current trick
  [120:124] phase_onehot       — [FLOR, ENVIDO, TRUCO, PLAY]
  [124:127] bid_levels         — [flor_stake/target, envido_stake/10, truco_stake/4]
  [127:133] has_flor           — [bool]*6 (who declared flor, public)
  [133:134] own_envido         — normalized [0,1]
  [134:135] own_flor_score     — normalized [0,1]
  [135:136] team_score         — scores[my_team] / target
  [136:137] opp_score          — scores[opp_team] / target
  [137:138] malas_my_team      — 1 if my team has < half target
  [138:139] malas_opp_team     — 1 if opp team has < half target
  [139:157] trick_winners      — 6*3 one-hot: which player won each trick
                                  (all zeros if trick not complete)
  [157:163] player_position    — one-hot seat index
  [163:169] team_membership    — [1 if same team as me] * 6
  [169:170] v_mc               — P(my team wins | random play from deal), or 0.0 if disabled
  [170:204] padding / reserved — zeros (34 dims)

Total = 204
"""

import numpy as np

from engine.game_state import TEAM_A, TEAM_B, GameState, team_of
from engine.phases import Phase
from engine.truco import NUMEROS

OBS_DIM = 204


def _card_idx(palo: int, numero: int) -> int:
    return palo * 10 + NUMEROS.index(numero)


def obs_to_vector(
    state: GameState,
    player_idx: int,
    v_mc: float | None = None,
) -> np.ndarray:
    """Return a float32 numpy array of shape (OBS_DIM,) for player_idx.

    Parameters
    ----------
    v_mc : float | None
        If provided, written to obs[169] as the MC-estimated win probability
        for the training agent's team under random play from the initial deal.
        Defaults to None (obs[169] stays 0.0 for backward compatibility).
    """
    obs = np.zeros(OBS_DIM, dtype=np.float32)
    p = player_idx
    my_team = team_of(p)
    opp_team = 1 - my_team
    half = state.target // 2

    # [0:40] own cards
    for card in state.cards_in_hand[p]:
        obs[_card_idx(*card)] = 1.0

    # [40:80] played cards (all cards no longer in any player's hand)
    for i in range(6):
        original = set(map(tuple, state.manos[i]))
        remaining = set(map(tuple, state.cards_in_hand[i]))
        for card in original - remaining:
            obs[40 + _card_idx(*card)] = 1.0

    # [80:120] current trick cards
    if state.phase == Phase.PLAY:
        for card in state.tricks[state.trick_num].values():
            obs[80 + _card_idx(*card)] = 1.0

    # [120:124] phase one-hot
    phase_map = {Phase.FLOR: 0, Phase.ENVIDO: 1, Phase.TRUCO: 2, Phase.PLAY: 3}
    if state.phase in phase_map:
        obs[120 + phase_map[state.phase]] = 1.0

    # [124:127] bid levels (normalized)
    obs[124] = min(state.flor_stake / max(state.target, 1), 1.0)
    obs[125] = min(state.envido_stake / 10.0, 1.0)
    obs[126] = state.truco_stake / 4.0

    # [127:133] has_flor (public after announcement)
    for i in range(6):
        obs[127 + i] = float(state.has_flor[i])

    # [133:135] own envido and flor (normalized)
    obs[133] = state.envido[p] / 37.0
    obs[134] = state.flor_score[p] / 47.0

    # [135:139] scores and malas
    obs[135] = state.scores[my_team] / state.target
    obs[136] = state.scores[opp_team] / state.target
    obs[137] = 1.0 if state.scores[my_team] < half else 0.0
    obs[138] = 1.0 if state.scores[opp_team] < half else 0.0

    # [139:157] trick winners — 6 players × 3 tricks
    for t in range(3):
        winner_team = state.trick_winners[t]
        if winner_team == -1:
            continue
        # Mark the player from the winning team who played the winning card
        winners_in_trick = [
            i for i in (TEAM_A if winner_team == 0 else TEAM_B) if i in state.tricks[t]
        ]
        if winners_in_trick:
            winner_p = winners_in_trick[0]
            obs[139 + t * 6 + winner_p] = 1.0

    # [157:163] player position one-hot
    obs[157 + p] = 1.0

    # [163:169] team membership
    for i in range(6):
        obs[163 + i] = 1.0 if team_of(i) == my_team else 0.0

    # [169] V_MC: MC-estimated win probability from initial deal (0.0 if disabled)
    if v_mc is not None:
        obs[169] = float(np.clip(v_mc, 0.0, 1.0))
    # [170:204] padding — zeros

    return obs
