"""
TrucoGame: full game loop for Truco Uruguayo (6-player, 2 teams of 3).

Simplifications vs. the real game (v1):
  - Flor: only the first flor player per team bids (2-player interaction).
  - Envido/Truco: all 6 players get an initiation turn; after a bid is made
    only the initiating player and the first opponent (in mano order) interact.
  - Truco bidding happens as a dedicated phase before card play (not interleaved).
  - Pico-a-pico mode not implemented; only redondilla (6 players per trick).
  - Falta envido pays `target - max(scores)` (simplified).
  - Contra flor al resto pays `target - winner's current score` (simplified).
"""

import random

from .actions import Action, action_to_card, card_to_action
from .card import card_strength
from .game_state import TEAM_A, TEAM_B, GameState, team_of
from .phases import Phase
from .truco import construir_mazo, simular_mano

# ── stake constants ────────────────────────────────────────────────────────

FLOR_CHICO_PTS = 3  # flor chico (first bid) is worth 3 pts
REAL_ENVIDO_PTS = 3  # real envido adds 3 pts to the stake
RETRUCO_PTS = 3  # retruco stake value

# ── helpers ────────────────────────────────────────────────────────────────


def _turn_order(lead: int, n: int = 6) -> list[int]:
    """Return list of n player indices starting from lead (wrapping)."""
    return [(lead + i) % n for i in range(n)]


def _first_in_team(start_player: int, team: int) -> int:
    """Return first player in `team` in mano-order starting from start_player."""
    for i in range(6):
        p = (start_player + i) % 6
        if team_of(p) == team:
            return p
    raise RuntimeError("No player in team")


# ── main class ─────────────────────────────────────────────────────────────


class TrucoGame:
    def __init__(self, target: int = 40):
        self.target = target
        self._mazo = construir_mazo()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self, seed: int | None = None, scores: list | None = None) -> GameState:
        """Deal a new hand and return the initial GameState."""
        rng = random.Random(seed)
        r = simular_mano(self._mazo, rng)

        manos = [list(hand) for hand in r["manos"]]
        muestra = r["muestra"]
        has_flor = r["flores"]
        envido = r["envidos"]
        flor_score = r["flores_pts"]
        game_scores = list(scores) if scores else [0, 0]

        state = GameState(
            manos=manos,
            muestra=muestra,
            has_flor=has_flor,
            envido=envido,
            flor_score=flor_score,
            cards_in_hand=[list(h) for h in manos],
            scores=game_scores,
            target=self.target,
            phase=Phase.DONE,  # will be set below
            current_player=0,
            # flor
            flor_bidder=-1,
            flor_responder=-1,
            flor_stake=0,
            flor_prev_stake=FLOR_CHICO_PTS,  # base flor fold value
            flor_bid_team=-1,
            # envido
            envido_bid_queue=[],
            envido_active_bidder=-1,
            envido_active_responder=-1,
            envido_stake=0,
            envido_prev_stake=1,  # base envido fold value
            envido_bid_team=-1,
            envido_is_falta=False,
            # truco
            truco_bid_queue=[],
            truco_active_bidder=-1,
            truco_active_responder=-1,
            truco_stake=0,
            truco_bid_team=-1,
            truco_folded=False,
            truco_fold_winner=-1,
            # play
            trick_num=0,
            tricks=[{}, {}, {}],
            trick_winners=[-1, -1, -1],
            lead_player=0,
            trick_play_order=list(range(6)),
            trick_play_idx=0,
            # hand pts
            hand_pts=[0, 0],
        )

        self._enter_first_phase(state)
        return state

    def legal_actions(self, state: GameState) -> list[Action]:
        """Return all legal actions for state.current_player."""
        p = state.current_player
        phase = state.phase

        if phase == Phase.FLOR:
            return self._flor_legal(state, p)
        if phase == Phase.ENVIDO:
            return self._envido_legal(state, p)
        if phase == Phase.TRUCO:
            return self._truco_legal(state, p)
        if phase == Phase.PLAY:
            return [card_to_action(*c) for c in state.cards_in_hand[p]]
        return []

    def apply_action(self, state: GameState, action: Action) -> GameState:
        """Apply action to state in-place; advance current_player/phase."""
        phase = state.phase
        if phase == Phase.FLOR:
            self._flor_action(state, action)
        elif phase == Phase.ENVIDO:
            self._envido_action(state, action)
        elif phase == Phase.TRUCO:
            self._truco_action(state, action)
        elif phase == Phase.PLAY:
            self._play_action(state, action)
        return state

    def is_terminal(self, state: GameState) -> bool:
        return state.phase == Phase.DONE

    def get_rewards(self, state: GameState) -> list[float]:
        """Per-player reward: +1 if hand won, -1 if lost, 0 if tied."""
        dA = state.hand_pts[0]
        dB = state.hand_pts[1]
        if dA > dB:
            return [1.0 if p in TEAM_A else -1.0 for p in range(6)]
        if dB > dA:
            return [-1.0 if p in TEAM_A else 1.0 for p in range(6)]
        return [0.0] * 6

    # ------------------------------------------------------------------
    # Phase entry helpers
    # ------------------------------------------------------------------

    def _enter_first_phase(self, state: GameState):
        """Set the opening phase after a deal."""
        if any(state.has_flor):
            self._enter_flor(state)
        else:
            self._enter_envido(state)

    def _enter_flor(self, state: GameState):
        flors_A = [p for p in TEAM_A if state.has_flor[p]]
        flors_B = [p for p in TEAM_B if state.has_flor[p]]

        if not flors_A and not flors_B:
            self._enter_envido(state)
            return

        # One-sided flor: auto-award, no bidding
        if not flors_A or not flors_B:
            team = 0 if flors_A else 1
            members = flors_A if flors_A else flors_B
            pts = 3 * len(members)
            state.hand_pts[team] += pts
            self._enter_truco(state)
            return

        # Both teams have flor: set up 2-player bidding
        # First flor player in mano order goes first
        first = next(p for p in range(6) if state.has_flor[p])
        first_team = team_of(first)
        opp_team = 1 - first_team
        resp = next(p for p in range(6) if state.has_flor[p] and team_of(p) == opp_team)

        state.flor_bidder = first
        state.flor_responder = resp
        state.flor_stake = 0
        state.flor_prev_stake = FLOR_CHICO_PTS  # fold on first bid
        state.flor_bid_team = -1
        state.phase = Phase.FLOR
        state.current_player = first

    def _enter_envido(self, state: GameState):
        state.envido_bid_queue = list(range(6))
        state.envido_active_bidder = -1
        state.envido_active_responder = -1
        state.envido_stake = 0
        state.envido_prev_stake = 1
        state.envido_bid_team = -1
        state.envido_is_falta = False
        state.phase = Phase.ENVIDO
        state.current_player = 0

    def _enter_truco(self, state: GameState):
        state.truco_bid_queue = list(range(6))
        state.truco_active_bidder = -1
        state.truco_active_responder = -1
        state.truco_stake = 0
        state.truco_bid_team = -1
        state.truco_folded = False
        state.truco_fold_winner = -1
        state.phase = Phase.TRUCO
        state.current_player = 0

    def _enter_play(self, state: GameState):
        state.trick_num = 0
        state.tricks = [{}, {}, {}]
        state.trick_winners = [-1, -1, -1]
        state.lead_player = 0
        state.trick_play_order = list(range(6))
        state.trick_play_idx = 0
        state.phase = Phase.PLAY
        state.current_player = 0

    # ------------------------------------------------------------------
    # Flor phase
    # ------------------------------------------------------------------

    def _flor_legal(self, state: GameState, p: int) -> list[Action]:
        stake = state.flor_stake
        bid_team = state.flor_bid_team
        my_team = team_of(p)

        if bid_team == -1:
            # No bid yet — must announce (no PASS available)
            actions = [Action.FLOR_CHICO]
            if True:  # can always offer con envido or contra resto
                actions.append(Action.FLOR_CON_ENVIDO)
            actions.append(Action.FLOR_CONTRA_RESTO)
            return actions

        if bid_team != my_team:
            # Opponent bid — respond
            actions = [Action.FOLD, Action.FLOR_PASS]
            if stake < 5:  # can raise to con envido
                actions.append(Action.FLOR_CON_ENVIDO)
            if stake < 9999:  # can always go to contra resto
                actions.append(Action.FLOR_CONTRA_RESTO)
            return actions

        # Same team bid (shouldn't happen in 2-player flor model)
        return [Action.FLOR_PASS]

    def _flor_action(self, state: GameState, action: Action):
        p = state.current_player
        my_team = team_of(p)
        opp_team = 1 - my_team

        if action == Action.FOLD:
            winning_team = opp_team
            pts = state.flor_prev_stake
            state.hand_pts[winning_team] += pts
            self._enter_truco(state)
            return

        if action == Action.FLOR_PASS:
            # Accept current stake → resolve by flor score comparison
            self._resolve_flor(state, state.flor_stake)
            self._enter_truco(state)
            return

        # Bid actions — set new stake
        if action == Action.FLOR_CHICO:
            state.flor_prev_stake = FLOR_CHICO_PTS
            state.flor_stake = FLOR_CHICO_PTS
        elif action == Action.FLOR_CON_ENVIDO:
            state.flor_prev_stake = state.flor_stake if state.flor_stake > 0 else FLOR_CHICO_PTS
            state.flor_stake = 5
        elif action == Action.FLOR_CONTRA_RESTO:
            state.flor_prev_stake = state.flor_stake if state.flor_stake > 0 else FLOR_CHICO_PTS
            # Contra resto: winner gets all points needed to win
            state.flor_stake = state.target - state.scores[my_team]

        state.flor_bid_team = my_team

        # Advance to opponent
        next_p = state.flor_responder if p == state.flor_bidder else state.flor_bidder
        state.current_player = next_p

    def _resolve_flor(self, state: GameState, pts: int):
        """Award flor pts to the team with the highest flor score."""
        max_A = max((state.flor_score[p] for p in TEAM_A if state.has_flor[p]), default=0)
        max_B = max((state.flor_score[p] for p in TEAM_B if state.has_flor[p]), default=0)
        if max_A > max_B:
            state.hand_pts[0] += pts
        elif max_B > max_A:
            state.hand_pts[1] += pts
        # Tie: no pts awarded (edge case; real rules have tie-break by mano)
        else:
            state.hand_pts[0] += pts  # mano (player 0, team A) wins ties

    # ------------------------------------------------------------------
    # Envido phase
    # ------------------------------------------------------------------

    def _envido_legal(self, state: GameState, p: int) -> list[Action]:
        bid_team = state.envido_bid_team
        my_team = team_of(p)
        is_falta = state.envido_is_falta

        if bid_team == -1:
            # No active bid — initiation turn
            return [
                Action.ENVIDO_PASS,
                Action.ENVIDO,
                Action.REAL_ENVIDO,
                Action.FALTA_ENVIDO,
            ]

        if bid_team != my_team:
            # Opponent has active bid — must respond
            if is_falta:
                return [Action.FOLD, Action.ENVIDO_PASS]
            return [
                Action.FOLD,
                Action.ENVIDO_PASS,  # accept
                Action.ENVIDO,
                Action.REAL_ENVIDO,
                Action.FALTA_ENVIDO,
            ]

        # Same team has bid: this shouldn't happen in normal flow
        return [Action.ENVIDO_PASS]

    def _envido_action(self, state: GameState, action: Action):
        p = state.current_player
        my_team = team_of(p)

        # ── No active bid: initiation turn ──
        if state.envido_bid_team == -1:
            if action == Action.ENVIDO_PASS:
                # Advance through initiation queue
                if state.envido_bid_queue:
                    state.envido_bid_queue.pop(0)
                if state.envido_bid_queue:
                    state.current_player = state.envido_bid_queue[0]
                else:
                    # All passed, no envido
                    self._enter_truco(state)
                return

            # Bid initiated
            self._envido_apply_bid(state, action, p)
            # Responder = first player in opposing team (in mano order)
            resp = _first_in_team(0, 1 - my_team)
            state.envido_active_bidder = p
            state.envido_active_responder = resp
            state.envido_bid_team = my_team
            state.envido_bid_queue = []  # no more initiation turns
            state.current_player = resp
            return

        # ── Active bid from opponent: respond ──
        if action == Action.FOLD:
            winning_team = state.envido_bid_team
            state.hand_pts[winning_team] += state.envido_prev_stake
            self._enter_truco(state)
            return

        if action == Action.ENVIDO_PASS:
            # Accept — resolve by score comparison
            pts = self._resolve_envido_pts(state)
            winner = self._envido_winner(state)
            state.hand_pts[winner] += pts
            self._enter_truco(state)
            return

        # Raise
        self._envido_apply_bid(state, action, p)
        # Bidder now becomes p; previous active bidder responds
        prev_bidder = state.envido_active_bidder
        state.envido_active_bidder = p
        state.envido_active_responder = prev_bidder
        state.envido_bid_team = my_team
        state.current_player = prev_bidder

    def _envido_apply_bid(self, state: GameState, action: Action, p: int):
        """Update envido stake for a bid action."""
        prev = state.envido_stake
        if action == Action.ENVIDO:
            state.envido_prev_stake = prev if prev > 0 else 1
            state.envido_stake += 2
        elif action == Action.REAL_ENVIDO:
            state.envido_prev_stake = prev if prev > 0 else 1
            state.envido_stake += REAL_ENVIDO_PTS
        elif action == Action.FALTA_ENVIDO:
            state.envido_prev_stake = prev if prev > 0 else 1
            state.envido_stake = state.target - max(state.scores)
            state.envido_is_falta = True

    def _envido_winner(self, state: GameState) -> int:
        """Return team with the highest envido score (0=A, 1=B)."""
        max_A = max(state.envido[p] for p in TEAM_A)
        max_B = max(state.envido[p] for p in TEAM_B)
        if max_A >= max_B:  # mano (team A) wins ties
            return 0
        return 1

    def _resolve_envido_pts(self, state: GameState) -> int:
        return max(state.envido_stake, 2)  # minimum 2 pts if accepted

    # ------------------------------------------------------------------
    # Truco phase
    # ------------------------------------------------------------------

    def _truco_legal(self, state: GameState, p: int) -> list[Action]:
        stake = state.truco_stake
        bid_team = state.truco_bid_team
        my_team = team_of(p)

        if bid_team == -1:
            # Initiation turn
            return [Action.TRUCO_PASS, Action.TRUCO]

        if bid_team != my_team:
            # Opponent bid — respond
            actions = [Action.FOLD, Action.TRUCO_PASS]
            if stake == 2:
                actions.append(Action.RETRUCO)
            if stake <= 3:
                actions.append(Action.VALE_CUATRO)
            return actions

        # Same team bid (after raise) — can keep raising or accept
        actions = [Action.TRUCO_PASS]  # accept
        if stake == 2:
            actions.append(Action.RETRUCO)
        if stake <= 3:
            actions.append(Action.VALE_CUATRO)
        return actions

    def _truco_action(self, state: GameState, action: Action):
        p = state.current_player
        my_team = team_of(p)

        # ── No active bid: initiation turn ──
        if state.truco_bid_team == -1:
            if action == Action.TRUCO_PASS:
                if state.truco_bid_queue:
                    state.truco_bid_queue.pop(0)
                if state.truco_bid_queue:
                    state.current_player = state.truco_bid_queue[0]
                else:
                    # All passed: truco stake = 0 (worth 1 pt base)
                    self._enter_play(state)
                return

            # TRUCO bid
            state.truco_stake = 2
            state.truco_bid_team = my_team
            state.truco_bid_queue = []
            resp = _first_in_team(0, 1 - my_team)
            state.truco_active_bidder = p
            state.truco_active_responder = resp
            state.current_player = resp
            return

        # ── Active bid ──
        if action == Action.FOLD:
            winning_team = state.truco_bid_team
            pts = max(state.truco_stake - 1, 1)  # fold gives stake - 1 (min 1)
            state.hand_pts[winning_team] += pts
            state.truco_folded = True
            state.truco_fold_winner = winning_team
            self._finish_hand(state)
            return

        if action == Action.TRUCO_PASS:
            # Accept current stake → go play cards
            self._enter_play(state)
            return

        # Raise
        if action == Action.RETRUCO:
            state.truco_stake = RETRUCO_PTS
        elif action == Action.VALE_CUATRO:
            state.truco_stake = 4

        state.truco_bid_team = my_team
        prev_bidder = state.truco_active_bidder
        state.truco_active_bidder = p
        state.truco_active_responder = prev_bidder
        state.current_player = prev_bidder

    # ------------------------------------------------------------------
    # Card play phase
    # ------------------------------------------------------------------

    def _play_action(self, state: GameState, action: Action):
        p = state.current_player
        card = action_to_card(action)

        # Remove card from hand and record in trick
        state.cards_in_hand[p].remove(card)
        state.tricks[state.trick_num][p] = card
        state.trick_play_idx += 1

        if state.trick_play_idx < 6:
            # More players to act in this trick
            state.current_player = state.trick_play_order[state.trick_play_idx]
            return

        # All 6 players played — resolve trick
        self._resolve_trick(state)

    def _resolve_trick(self, state: GameState):
        t = state.trick_num
        pm, nm = state.muestra
        played = state.tricks[t]

        def _strength(player):
            palo, num = played[player]
            return card_strength(palo, num, pm, nm)

        # Find max strength per team
        max_A = max((_strength(p) for p in TEAM_A if p in played), default=-1)
        max_B = max((_strength(p) for p in TEAM_B if p in played), default=-1)

        if max_A > max_B:
            winner_team = 0
        elif max_B > max_A:
            winner_team = 1
        else:
            winner_team = -1  # tie

        state.trick_winners[t] = winner_team

        # Determine next lead player
        if winner_team == -1:
            next_lead = state.lead_player
        else:
            max_s = max_A if winner_team == 0 else max_B
            team_players = TEAM_A if winner_team == 0 else TEAM_B
            # First in play order from winning team with max strength
            next_lead = state.lead_player  # fallback
            for player in state.trick_play_order:
                if player in team_players and player in played and _strength(player) == max_s:
                    next_lead = player
                    break

        # Check for early termination (winner decided after 2 tricks)
        if t >= 1:
            early_winner = self._check_early_winner(state, t)
            if early_winner is not None:
                self._award_truco(state, early_winner)
                self._finish_hand(state)
                return

        if t == 2:
            # All 3 tricks done
            full_winner = self._compute_hand_winner(state)
            self._award_truco(state, full_winner)
            self._finish_hand(state)
            return

        # Advance to next trick
        state.trick_num += 1
        state.lead_player = next_lead
        state.trick_play_order = _turn_order(next_lead)
        state.trick_play_idx = 0
        state.current_player = next_lead

    def _check_early_winner(self, state: GameState, last_t: int) -> int | None:
        """Return winning team if decidable before all 3 tricks, else None."""
        w = state.trick_winners
        wins_A = sum(1 for x in w[: last_t + 1] if x == 0)
        wins_B = sum(1 for x in w[: last_t + 1] if x == 1)

        if wins_A >= 2:
            return 0
        if wins_B >= 2:
            return 1

        # After trick 1 (index 1): some tie scenarios decide the hand
        if last_t == 1:
            r0, r1 = w[0], w[1]
            # A wins trick 0, tie trick 1 → A wins
            if r0 == 0 and r1 == -1:
                return 0
            # B wins trick 0, tie trick 1 → B wins
            if r0 == 1 and r1 == -1:
                return 1
            # Tie trick 0, A wins trick 1 → A wins
            if r0 == -1 and r1 == 0:
                return 0
            # Tie trick 0, B wins trick 1 → B wins
            if r0 == -1 and r1 == 1:
                return 1

        return None  # need more tricks

    def _compute_hand_winner(self, state: GameState) -> int:
        """Full tie-breaking logic after all 3 tricks."""
        w = state.trick_winners
        wins_A = w.count(0)
        wins_B = w.count(1)

        if wins_A >= 2:
            return 0
        if wins_B >= 2:
            return 1

        r0, r1, r2 = w[0], w[1], w[2]

        # A won r0, B won r1, tie r2 → A wins (won first)
        if r0 == 0 and r1 == 1 and r2 == -1:
            return 0
        # B won r0, A won r1, tie r2 → B wins (won first)
        if r0 == 1 and r1 == 0 and r2 == -1:
            return 1

        # All ties → mano wins (player 0, team A)
        return 0

    def _award_truco(self, state: GameState, winning_team: int):
        """Award truco points to winning team."""
        if state.truco_folded:
            return  # already awarded when fold happened
        pts = max(state.truco_stake, 1)  # 0 stake = base 1 pt
        state.hand_pts[winning_team] += pts

    # ------------------------------------------------------------------
    # Hand completion
    # ------------------------------------------------------------------

    def _finish_hand(self, state: GameState):
        """Finalise hand: add hand pts to cumulative scores, set DONE."""
        state.scores[0] += state.hand_pts[0]
        state.scores[1] += state.hand_pts[1]
        state.phase = Phase.DONE
