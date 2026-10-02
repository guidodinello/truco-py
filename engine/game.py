"""
TrucoGame: one hand of Truco Uruguayo (6 players in 2 teams of 3, or a
mano-a-mano pair of a pico-a-pico round), written against ``docs/rules.md``.

A hand runs: [«a ley de juego»] → [flor contest] → three tricks. Envido and
truco are called **inside a player's turn** in the tricks, as in the real game:

  - Truco may be called by any player in their turn (S3 L89; S2 Art 49–50).
    The side that accepted a call may raise it later, in any turn of any of its
    players (S3 L91; S2 Art 63–64). Vale cuatro only answers a retruco.
  - Envido may be called by a player who still holds three cards and has not
    said truco or «quiero» to one (S2 Art 22), and also in answer to a truco
    («el envido va primero», S2 Art 60). Raises must be at least the call they
    answer (S2 Art 35); totals are capped at the falta (S2 Art 36).
  - Flor voids envido (S2 Art 27). Both sides' flor holders contest with the
    same envite ladder «con flor» plus contra flor al resto (S2 Art 31–37).
  - Ties in envido / flor follow the declaration procedure (S2 Art 39–40).
  - A player may «paso» (out, teammates play on) or go to the mazo (the whole
    side is out) on their turn (S2 Art 88–90).

Simplifications that remain (see ``docs/engine-rules-audit.md``):
  - A pending call is answered by one seat: the first rival in play to the
    caller's right (any player of the side may answer in the real game, after
    consulting; who answers is fixed here rather than chosen by the side).
  - Envites are a fixed menu (envido, real envido ×1/×2/×3, hasta igualar,
    falta); free-form «N tantos envido» amounts are not offered.
  - Flor is announced automatically (holders are obliged to sing it, S2 Art 16)
    and contested before the first card; penalties for negar / canto errado
    (S2 Art 46–47) cannot arise.
  - Envido + truco «in one breath» (S2 Art 69) is played as two calls in the same
    turn: envido first, then truco, which S2 Art 69 says is the answer order.
  - When a side reaches the chico's points through envido / flor the hand ends
    at once (S2 Art 80 states this for the ley de juego; common practice).
"""

import random

from .actions import (
    ENVIDO_CALLS,
    LEY_BUNDLES,
    Action,
    action_to_card,
    card_to_action,
)
from .card import card_strength
from .game_state import (
    ENVITE_ENVIDO,
    ENVITE_FLOR,
    NO_ENVITE,
    TEAM_A,
    Card,
    Deal,
    GameState,
    team_of,
)
from .phases import Phase
from .rules import Rules, capped_total, declaration_winner, falta, hand_winner, turn_order
from .truco import calcular_envido, calcular_flor, construir_mazo, simular_mano, tiene_flor

# ── stake constants ────────────────────────────────────────────────────────

FLOR_PTS = 3  # each flor is worth 3 (S2 Art 20; S3 L134)
DECLINED_ENVIDO_PTS = 1  # a declined first envido pays 1 (S2 Art 24)
DECLINED_TRUCO_PTS = 1  # a declined truco pays 1 (S2 Art 61)
ENVITE_AMOUNTS = {
    Action.ENVIDO: 2,
    Action.REAL_ENVIDO: 3,
    Action.DOS_REAL_ENVIDO: 2 * 3,  # «real envido» with a number: that number × 3 (S2 Art 24)
    Action.TRES_REAL_ENVIDO: 3 * 3,
}
TRUCO_RAISE = {2: Action.TRUCO, 3: Action.RETRUCO, 4: Action.VALE_CUATRO}  # level → call
MAX_TRUCO_LEVEL = 4

# Which parts each «a ley de juego» bundle names (S2 Art 73): (falta, resto, truco)
LEY_PARTS: dict[Action, tuple[bool, bool, bool]] = {
    Action.LEY_TODO: (True, True, True),
    Action.LEY_FALTA: (True, False, False),
    Action.LEY_RESTO: (False, True, False),
    Action.LEY_FALTA_RESTO: (True, True, False),
    Action.LEY_FALTA_TRUCO: (True, False, True),
    Action.LEY_TRUCO: (False, False, True),
    Action.LEY_RESTO_TRUCO: (False, True, True),
}


def make_deal(manos: list[list[Card]], muestra: Card) -> Deal:
    """Build a Deal (envido and flor computed) from explicit hands."""
    pm, nm = muestra
    flores = tuple(tiene_flor(m, pm, nm) for m in manos)
    return Deal(
        manos=tuple(tuple(m) for m in manos),
        muestra=muestra,
        has_flor=flores,
        envido=tuple(calcular_envido(m, pm, nm) for m in manos),
        flor_score=tuple(
            calcular_flor(m, pm, nm) if f else 0 for m, f in zip(manos, flores, strict=True)
        ),
    )


def deal_from_seed(seed: int | None) -> Deal:
    """Shuffle a fresh deck, so the same seed always gives the same deal (#25)."""
    r = simular_mano(construir_mazo(), random.Random(seed))
    return make_deal([list(h) for h in r["manos"]], r["muestra"])


# ── main class ─────────────────────────────────────────────────────────────


class TrucoGame:
    def __init__(self, target: int = 40, rules: Rules | None = None):
        self.rules = rules if rules is not None else Rules(chico_points=target)
        self.target = self.rules.chico_points

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: int | None = None,
        scores: list[int] | None = None,
        *,
        mano: int = 0,
        seats: list[int] | None = None,
        deal: Deal | None = None,
        falta_cap: int | None = None,
    ) -> GameState:
        """Deal a new hand and return its initial GameState.

        ``seats`` restricts the hand to some players (a mano-a-mano pair);
        ``deal`` replays a given deal instead of shuffling; ``falta_cap`` caps
        the falta and the resto (S2 Art 86 in mano-a-mano rounds).
        """
        d = deal if deal is not None else deal_from_seed(seed)
        table = sorted(seats) if seats is not None else list(range(6))
        order = turn_order(mano, table)
        game_scores = list(scores) if scores else [0, 0]

        state = GameState(
            manos=[list(hand) for hand in d.manos],
            muestra=d.muestra,
            has_flor=list(d.has_flor),
            envido=list(d.envido),
            flor_score=list(d.flor_score),
            seats=table,
            mano=order[0],
            order=order,
            in_play=[s in table for s in range(6)],
            cards_in_hand=[list(h) for h in d.manos],
            scores=game_scores,
            target=self.target,
            falta=falta(game_scores, self.target, falta_cap),
            phase=Phase.DONE,  # set below
            current_player=order[0],
            # ley de juego
            ley_offered=[False, False],
            ley_team=-1,
            ley_bundle=-1,
            ley_caller=-1,
            # envites
            flor_holders=[s for s in order if d.has_flor[s]],
            flor_passed=[False, False],
            envite_kind=NO_ENVITE,
            envite_team=-1,
            envite_caller=-1,
            envite_total=0,
            envite_accepted=0,
            envite_last_amount=0,
            envite_calls=0,
            envite_contra=False,
            envite_banned_team=-1,
            envido_done=False,
            resume_phase=Phase.PLAY,
            # truco
            truco_level=1,
            truco_pending=False,
            truco_team=-1,
            truco_raise_team=-1,
            truco_responder=-1,
            spoke_truco=[False] * 6,
            resume_player=-1,
            # play
            trick_num=0,
            tricks=[{}, {}, {}],
            trick_winners=[-1, -1, -1],
            lead_player=order[0],
            trick_play_order=list(order),
            trick_play_idx=0,
            hand_pts=[0, 0],
        )

        if self.rules.ley_de_juego:
            self._offer_ley(state, self._ley_preferred_team(state))
        else:
            self._start_flor(state)
        return state

    def legal_actions(self, state: GameState) -> list[Action]:
        """Return all legal actions for state.current_player."""
        p = state.current_player
        phase = state.phase
        if phase == Phase.PLAY:
            return self._play_legal(state, p)
        if phase == Phase.TRUCO:
            return self._truco_answers(state, p)
        if phase == Phase.ENVIDO:
            return self._envite_answers(state, p)
        if phase == Phase.FLOR:
            if state.envite_team == -1:
                return self._flor_opening(state, p)
            return self._envite_answers(state, p)
        if phase == Phase.LEY:
            return self._ley_legal(state)
        return []

    def apply_action(self, state: GameState, action: Action) -> GameState:
        """Apply action to state in-place; advance current_player/phase."""
        phase = state.phase
        if phase == Phase.PLAY:
            self._play_action(state, action)
        elif phase == Phase.TRUCO:
            self._truco_answer(state, action)
        elif phase in (Phase.ENVIDO, Phase.FLOR):
            self._envite_action(state, action)
        elif phase == Phase.LEY:
            self._ley_action(state, action)
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
    # Helpers
    # ------------------------------------------------------------------

    def _answerer(self, state: GameState, caller: int, flor_only: bool = False) -> int:
        """First rival in play to the caller's right (who answers a call)."""
        order = state.order
        i = order.index(caller)
        for k in range(1, len(order) + 1):
            s = order[(i + k) % len(order)]
            if (
                team_of(s) != team_of(caller)
                and state.in_play[s]
                and (not flor_only or s in state.flor_holders)
            ):
                return s
        raise RuntimeError("no rival in play to answer the call")

    def _award(self, state: GameState, team: int, pts: int) -> None:
        state.hand_pts[team] += pts

    def _target_reached(self, state: GameState) -> bool:
        return any(state.scores[t] + state.hand_pts[t] >= state.target for t in (0, 1))

    def _flors(self, state: GameState, team: int) -> int:
        return sum(1 for s in state.flor_holders if team_of(s) == team)

    # ------------------------------------------------------------------
    # «A ley de juego» (S2 Art 70–82)
    # ------------------------------------------------------------------

    def _ley_preferred_team(self, state: GameState) -> int:
        """The side behind on points, or mano's side on equal points (S2 Art 71)."""
        a, b = state.scores
        if a != b:
            return 0 if a < b else 1
        return team_of(state.mano)

    def _offer_ley(self, state: GameState, team: int) -> None:
        state.ley_offered[team] = True
        state.phase = Phase.LEY
        state.current_player = next(s for s in state.order if team_of(s) == team)

    def _ley_envite(self, state: GameState) -> str | None:
        """The envite a ley bundle actually puts at stake: the resto if both sides
        hold flor, the falta if nobody does, else none (S2 Art 27, 77–78)."""
        falta_in, resto_in, _ = LEY_PARTS[Action(state.ley_bundle)]
        flor_sides = {team_of(s) for s in state.flor_holders}
        if resto_in and len(flor_sides) == 2:
            return "resto"
        if falta_in and not flor_sides:
            return "falta"
        return None

    def _ley_legal(self, state: GameState) -> list[Action]:
        if state.ley_team == -1:
            return [Action.LEY_PASS, *LEY_BUNDLES]
        actions = [Action.QUIERO, Action.FOLD]
        if self._ley_envite(state) is not None and LEY_PARTS[Action(state.ley_bundle)][2]:
            actions += [Action.LEY_QUIERO_ENVITE, Action.LEY_QUIERO_TRUCO]
        return actions

    def _ley_action(self, state: GameState, action: Action) -> None:
        p = state.current_player
        if state.ley_team == -1:
            if action == Action.LEY_PASS:
                other = 1 - team_of(p)
                if not state.ley_offered[other]:
                    self._offer_ley(state, other)
                else:
                    self._start_flor(state)
                return
            state.ley_team = team_of(p)
            state.ley_bundle = int(action)
            state.ley_caller = p
            envite = self._ley_envite(state)
            truco_in = LEY_PARTS[action][2]
            if envite is None:
                # The challenger omitted the envite that applies: it may not envite
                # this hand (S2 Art 78); the challenged side may.
                state.envite_banned_team = state.ley_team
                if not truco_in:
                    self._start_flor(state)
                    return
            state.current_player = next(s for s in state.order if team_of(s) != state.ley_team)
            return

        # Answer, given once for every part (S2 Art 75)
        envite = self._ley_envite(state)
        truco_in = LEY_PARTS[Action(state.ley_bundle)][2]
        accept_envite = action in (Action.QUIERO, Action.LEY_QUIERO_ENVITE)
        accept_truco = action in (Action.QUIERO, Action.LEY_QUIERO_TRUCO)
        challenger = state.ley_team

        if envite is not None:
            state.envido_done = True
            if envite == "falta":
                if accept_envite:
                    winner = self._envido_winner(state)
                    self._award(state, winner, state.falta)
                else:
                    self._award(state, challenger, DECLINED_ENVIDO_PTS)
            elif accept_envite:  # resto, contra flor: winner collects every flor (S2 Art 31)
                winner = self._flor_winner(state)
                self._award(state, winner, state.falta + FLOR_PTS * len(state.flor_holders))
            else:  # declined: the challenger collects only its own flors (S2 Art 32)
                self._award(state, challenger, FLOR_PTS * self._flors(state, challenger))
            if self._target_reached(state):
                self._finish_hand(state)
                return

        if truco_in:
            if not accept_truco:
                self._award(state, challenger, DECLINED_TRUCO_PTS)
                self._finish_hand(state)
                return
            state.truco_level = 2
            state.truco_raise_team = 1 - challenger
            state.spoke_truco[state.ley_caller] = True
            state.spoke_truco[p] = True

        self._start_flor(state)

    # ------------------------------------------------------------------
    # Flor (S2 Art 16–20, 27–37)
    # ------------------------------------------------------------------

    def _start_flor(self, state: GameState) -> None:
        holders = state.flor_holders
        if state.envido_done or not holders:
            self._start_play(state)
            return
        # Any flor voids envido for the whole hand (S2 Art 27): flor_holders is
        # non-empty from here on, which closes _envido_open_for.
        sides = {team_of(s) for s in holders}
        if len(sides) == 1:
            # One side only: 3 per flor, no contest (S3 L134; S2 Art 20)
            state.envido_done = True
            self._award(state, sides.pop(), FLOR_PTS * len(holders))
            if self._target_reached(state):
                self._finish_hand(state)
                return
            self._start_play(state)
            return
        state.envite_kind = ENVITE_FLOR
        state.resume_phase = Phase.PLAY
        state.phase = Phase.FLOR
        state.current_player = holders[0]

    def _flor_opening(self, state: GameState, p: int) -> list[Action]:
        """A flor holder speaks: envite «con flor», or leave it to the comparison."""
        actions = [Action.FLOR_PASS]
        if team_of(p) != state.envite_banned_team and not state.spoke_truco[p]:
            actions += self._envite_calls(state, p, first=True)
        return actions

    def _flor_winner(self, state: GameState) -> int:
        values = {s: state.flor_score[s] for s in state.flor_holders}
        return declaration_winner(values, state.order)

    # ------------------------------------------------------------------
    # Envites — shared by envido and the flor contest
    # ------------------------------------------------------------------

    def _envido_open_for(self, state: GameState, p: int) -> bool:
        """May p start an envido now? (S2 Art 22, 27)"""
        return (
            not state.envido_done
            and state.envite_kind == NO_ENVITE
            and not state.flor_holders
            and state.trick_num == 0
            and len(state.cards_in_hand[p]) == 3
            and not state.spoke_truco[p]
            and team_of(p) != state.envite_banned_team
        )

    def _envite_calls(self, state: GameState, p: int, first: bool) -> list[Action]:
        """Calls p may make: an opening call (``first``) or a raise of the pending one."""
        limit = state.falta
        flor = state.envite_kind == ENVITE_FLOR
        contra = [Action.CONTRA_FLOR_AL_RESTO] if flor and not state.envite_contra else []
        old_total = 0 if first else state.envite_total
        if old_total >= limit:
            # Falta reached: only contra flor al resto can still be called (S2 Art 37)
            return contra
        min_amount = 0 if first else state.envite_last_amount
        calls = []
        for action, amount in ENVITE_AMOUNTS.items():
            fits = old_total + amount <= limit
            if amount >= min_amount and (fits or (first and action == Action.ENVIDO)):
                calls.append(action)
        gap = max(state.scores) - state.scores[team_of(p)]
        if gap > 0 and gap >= min_amount and old_total + gap <= limit:
            calls.append(Action.HASTA_IGUALAR)
        calls.append(Action.FALTA_ENVIDO)
        return calls + contra

    def _can_raise(self, state: GameState, p: int) -> bool:
        """Raising needs the same conditions as calling (S2 Art 35 → Art 22, 28)."""
        if team_of(p) == state.envite_banned_team or state.spoke_truco[p]:
            return False
        if state.envite_kind == ENVITE_ENVIDO:
            return len(state.cards_in_hand[p]) == 3
        return True

    def _envite_answers(self, state: GameState, p: int) -> list[Action]:
        actions = [Action.QUIERO, Action.FOLD]
        if self._can_raise(state, p):
            actions += self._envite_calls(state, p, first=False)
        return actions

    def _envite_action(self, state: GameState, action: Action) -> None:
        p = state.current_player
        if action == Action.FLOR_PASS:
            state.flor_passed[team_of(p)] = True
            other = 1 - team_of(p)
            if state.flor_passed[other]:
                # Nobody envited: compare flors, winner takes its side's flors (S2 Art 20)
                winner = self._flor_winner(state)
                self._award(state, winner, FLOR_PTS * self._flors(state, winner))
                self._settle_envite(state)
            else:
                state.current_player = next(s for s in state.flor_holders if team_of(s) == other)
            return
        if action == Action.QUIERO:
            self._accept_envite(state)
            return
        if action == Action.FOLD:
            self._decline_envite(state)
            return
        self._call_envite(state, action, p, first=state.envite_team == -1)

    def _call_envite(self, state: GameState, action: Action, p: int, first: bool) -> None:
        limit = state.falta
        old_total = 0 if first else state.envite_total
        if action in (Action.FALTA_ENVIDO, Action.CONTRA_FLOR_AL_RESTO):
            amount = total = limit
        else:
            if action == Action.HASTA_IGUALAR:
                amount = max(state.scores) - state.scores[team_of(p)]
            else:
                amount = ENVITE_AMOUNTS[action]
            total = capped_total(old_total, amount, state.envite_last_amount, limit, first)
        # A raise accepts the call it answers (S2 Art 34)
        state.envite_accepted = 0 if first else old_total
        state.envite_total = total
        state.envite_last_amount = amount
        state.envite_calls += 1
        state.envite_team = team_of(p)
        state.envite_caller = p
        if action == Action.CONTRA_FLOR_AL_RESTO:
            state.envite_contra = True
        if state.envite_kind == ENVITE_FLOR:
            state.current_player = self._answerer(state, p, flor_only=True)
        else:
            state.current_player = self._answerer(state, p)

    def _accept_envite(self, state: GameState) -> None:
        if state.envite_kind == ENVITE_ENVIDO:
            winner = self._envido_winner(state)
            pts = state.envite_total
        else:
            # «con flor»: tantos + the winner's side's flors; «contra flor» also the
            # rival's flors (S2 Art 31)
            winner = self._flor_winner(state)
            pts = state.envite_total + FLOR_PTS * self._flors(state, winner)
            if state.envite_contra:
                pts += FLOR_PTS * self._flors(state, 1 - winner)
        self._award(state, winner, pts)
        self._settle_envite(state)

    def _decline_envite(self, state: GameState) -> None:
        caller = state.envite_team
        first = state.envite_calls == 1
        if state.envite_kind == ENVITE_ENVIDO:
            # First call declined: 1; a raise declined: what was already accepted
            # (S2 Art 24, 35; S3 L111)
            pts = DECLINED_ENVIDO_PTS if first else state.envite_accepted
        else:
            # The caller collects its side's flors, plus what was accepted for a raise;
            # a declined contra flor raise also pays the rival's flors (S2 Art 32)
            pts = FLOR_PTS * self._flors(state, caller)
            if not first:
                pts += state.envite_accepted
                if state.envite_contra:
                    pts += FLOR_PTS * self._flors(state, 1 - caller)
        self._award(state, caller, pts)
        self._settle_envite(state)

    def _settle_envite(self, state: GameState) -> None:
        kind = state.envite_kind
        state.envido_done = True
        state.envite_team = -1
        if self._target_reached(state):
            self._finish_hand(state)
            return
        if kind == ENVITE_FLOR:
            self._start_play(state)
        elif state.resume_phase == Phase.TRUCO:
            state.phase = Phase.TRUCO
            state.current_player = state.truco_responder
        else:
            state.phase = Phase.PLAY
            state.current_player = state.resume_player

    def _envido_winner(self, state: GameState) -> int:
        values = {s: state.envido[s] for s in state.order if state.in_play[s]}
        return declaration_winner(values, state.order)

    def _start_envido(self, state: GameState, action: Action, p: int, resume: Phase) -> None:
        state.envite_kind = ENVITE_ENVIDO
        state.resume_phase = resume
        state.phase = Phase.ENVIDO
        self._call_envite(state, action, p, first=True)

    # ------------------------------------------------------------------
    # Truco (S1 Art 42–48; S2 Art 49–67)
    # ------------------------------------------------------------------

    def _truco_call(self, state: GameState, p: int) -> list[Action]:
        """The truco call p may make on their turn, if any."""
        if state.truco_level >= MAX_TRUCO_LEVEL:
            return []
        if state.truco_level == 1 and state.truco_raise_team == -1:
            return [Action.TRUCO]
        if state.truco_raise_team == team_of(p):
            return [TRUCO_RAISE[state.truco_level + 1]]
        return []

    def _call_truco(self, state: GameState, p: int) -> None:
        state.truco_pending = True
        state.truco_team = team_of(p)
        state.spoke_truco[p] = True
        state.truco_responder = self._answerer(state, p)
        state.phase = Phase.TRUCO
        state.current_player = state.truco_responder

    def _truco_answers(self, state: GameState, p: int) -> list[Action]:
        actions = [Action.QUIERO, Action.FOLD]
        pending = state.truco_level + 1
        if pending < MAX_TRUCO_LEVEL:
            actions.append(TRUCO_RAISE[pending + 1])  # retruco answers truco, vale cuatro retruco
        if self._envido_open_for(state, p):
            actions += self._envite_calls(state, p, first=True)  # «el envido va primero»
        return actions

    def _truco_answer(self, state: GameState, action: Action) -> None:
        p = state.current_player
        if action in ENVIDO_CALLS:
            self._start_envido(state, action, p, resume=Phase.TRUCO)
            return
        if action == Action.FOLD:
            # «No quiero»: the caller takes the value already accepted (S2 Art 61, 63, 64)
            self._award(state, state.truco_team, state.truco_level)
            self._finish_hand(state)
            return
        # QUIERO, or a raise (which accepts the call it answers, S2 Art 66)
        state.truco_level += 1
        state.truco_pending = False
        state.spoke_truco[p] = True
        state.truco_raise_team = team_of(p)
        state.truco_team = -1
        if action == Action.QUIERO:
            state.phase = Phase.PLAY
            state.current_player = state.resume_player
            return
        self._call_truco(state, p)

    # ------------------------------------------------------------------
    # Card play
    # ------------------------------------------------------------------

    def _start_play(self, state: GameState) -> None:
        state.phase = Phase.PLAY
        state.trick_num = 0
        state.lead_player = state.order[0]
        state.trick_play_order = [s for s in state.order if state.in_play[s]]
        state.trick_play_idx = 0
        state.current_player = state.trick_play_order[0]

    def _play_legal(self, state: GameState, p: int) -> list[Action]:
        actions = [card_to_action(*c) for c in state.cards_in_hand[p]]
        actions += self._truco_call(state, p)
        if self._envido_open_for(state, p):
            actions += self._envite_calls(state, p, first=True)
        if self._teammates_in_play(state, p):
            actions.append(Action.PASO)
        actions.append(Action.MAZO)
        return actions

    def _teammates_in_play(self, state: GameState, p: int) -> bool:
        return any(state.in_play[s] and team_of(s) == team_of(p) and s != p for s in state.order)

    def _play_action(self, state: GameState, action: Action) -> None:
        p = state.current_player
        state.resume_player = p
        if action in ENVIDO_CALLS:
            self._start_envido(state, action, p, resume=Phase.PLAY)
            return
        if action in (Action.TRUCO, Action.RETRUCO, Action.VALE_CUATRO):
            self._call_truco(state, p)
            return
        if action == Action.PASO:
            state.in_play[p] = False
            self._advance_turn(state)
            return
        if action == Action.MAZO:
            for s in state.order:
                if team_of(s) == team_of(p):
                    state.in_play[s] = False
            self._concede(state, team_of(p))
            return

        card = action_to_card(action)
        state.cards_in_hand[p].remove(card)
        state.tricks[state.trick_num][p] = card
        self._advance_turn(state)

    def _concede(self, state: GameState, team: int) -> None:
        """A side has nobody left in play: the rival wins the hand's truco value."""
        self._award(state, 1 - team, state.truco_level)
        self._finish_hand(state)

    def _advance_turn(self, state: GameState) -> None:
        for team in (0, 1):
            if not any(state.in_play[s] and team_of(s) == team for s in state.order):
                self._concede(state, team)
                return
        order = state.trick_play_order
        played = state.tricks[state.trick_num]
        for i in range(state.trick_play_idx + 1, len(order)):
            if state.in_play[order[i]] and order[i] not in played:
                state.trick_play_idx = i
                state.current_player = order[i]
                return
        self._resolve_trick(state)

    def _resolve_trick(self, state: GameState) -> None:
        t = state.trick_num
        pm, nm = state.muestra
        played = {s: c for s, c in state.tricks[t].items() if state.in_play[s]}

        def _strength(player: int) -> int:
            palo, num = played[player]
            return card_strength(palo, num, pm, nm)

        best = [
            max((_strength(s) for s in played if team_of(s) == team), default=-1) for team in (0, 1)
        ]
        in_order = [s for s in state.trick_play_order if s in played]
        if best[0] == best[1]:
            winner_team = -1
            # Parda: the most-mano player still in play leads (S1 Art 39; S2 Art 57)
            next_lead = next(s for s in state.order if state.in_play[s])
        else:
            winner_team = 0 if best[0] > best[1] else 1
            top = best[winner_team]
            next_lead = next(
                s for s in in_order if team_of(s) == winner_team and _strength(s) == top
            )
        state.trick_winners[t] = winner_team

        mano_team = team_of(next(s for s in state.order if state.in_play[s]))
        winner = hand_winner(state.trick_winners[: t + 1], mano_team)
        if winner is not None:
            self._award(state, winner, state.truco_level)
            self._finish_hand(state)
            return

        state.trick_num += 1
        state.lead_player = next_lead
        state.trick_play_order = [s for s in turn_order(next_lead, state.seats) if state.in_play[s]]
        state.trick_play_idx = 0
        state.current_player = next_lead

    # ------------------------------------------------------------------
    # Hand completion
    # ------------------------------------------------------------------

    def _finish_hand(self, state: GameState) -> None:
        """Finalise hand: add hand pts to cumulative scores, set DONE."""
        state.truco_pending = False
        state.envite_team = -1
        state.scores[0] += state.hand_pts[0]
        state.scores[1] += state.hand_pts[1]
        state.phase = Phase.DONE
