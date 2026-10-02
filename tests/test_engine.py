"""Tests for the TrucoGame hand engine, one block per rule (docs/rules.md) and per
audit finding (docs/engine-rules-audit.md)."""

import random

import pytest

from engine.actions import ENVIDO_CALLS, Action, card_to_action, is_card_action
from engine.game import TrucoGame, make_deal
from engine.game_state import Card, Deal, GameState, team_of
from engine.phases import Phase
from engine.rules import Rules
from engine.truco import construir_mazo, tiene_flor

ESP, BAS, COP, ORO = 0, 1, 2, 3
MUESTRA: Card = (COP, 12)  # a 12 muestra: the piezas are the 2, 4, 5, 10, 11 of copa


@pytest.fixture
def game() -> TrucoGame:
    return TrucoGame()


def _deal(hands: dict[int, list[Card]], muestra: Card = MUESTRA) -> Deal:
    """A deal with the given hands; the other seats get flor-free filler hands."""
    used = {muestra, *(c for h in hands.values() for c in h)}
    pool = [c for c in construir_mazo() if c not in used and c[0] != muestra[0]]
    manos: list[list[Card]] = []
    for seat in range(6):
        if seat in hands:
            manos.append(list(hands[seat]))
            continue
        # one card per suit never makes a flor (no copa: no piezas)
        hand = [next(c for c in pool if c[0] == suit) for suit in (ESP, BAS, ORO)]
        for c in hand:
            pool.remove(c)
        assert not tiene_flor(hand, *muestra)
        manos.append(hand)
    return make_deal(manos, muestra)


def _scripted(
    *,
    envido: list[int] | None = None,
    flor: dict[int, int] | None = None,
) -> Deal:
    """A deal whose envido / flor figures are given directly (cards are filler)."""
    base = _deal({})
    flor = flor or {}
    return Deal(
        manos=base.manos,
        muestra=base.muestra,
        has_flor=tuple(s in flor for s in range(6)),
        envido=tuple(envido) if envido else base.envido,
        flor_score=tuple(flor.get(s, 0) for s in range(6)),
    )


# Two flor hands for the contest tests: flor derecha of espadas and of bastos
FLOR_ESP = [(ESP, 1), (ESP, 7), (ESP, 6)]  # 1 + 7 + 6 + 20 = 34
FLOR_BAS = [(BAS, 1), (BAS, 3), (BAS, 4)]  # 1 + 3 + 4 + 20 = 28


def _play_card(game: TrucoGame, state: GameState) -> None:
    game.apply_action(state, next(a for a in game.legal_actions(state) if is_card_action(a)))


def _accept_everything(game: TrucoGame, state: GameState) -> None:
    """Answer every pending call with QUIERO and play the first card otherwise."""
    while state.phase != Phase.DONE:
        legal = game.legal_actions(state)
        if Action.QUIERO in legal:
            game.apply_action(state, Action.QUIERO)
        elif Action.FLOR_PASS in legal:
            game.apply_action(state, Action.FLOR_PASS)
        else:
            _play_card(game, state)


# ──────────────────────────────────────────────────────────────────────────
# Basics
# ──────────────────────────────────────────────────────────────────────────


def test_reset_returns_game_state(game: TrucoGame):
    assert isinstance(game.reset(seed=0), GameState)


def test_reset_deals_three_cards_per_player(game: TrucoGame):
    state = game.reset(seed=0)
    for i in range(6):
        assert len(state.manos[i]) == 3
        assert len(state.cards_in_hand[i]) == 3


def test_reset_scores_zero(game: TrucoGame):
    state = game.reset(seed=0)
    assert state.scores == [0, 0]


def test_reset_with_scores(game: TrucoGame):
    assert game.reset(seed=1, scores=[10, 20]).scores == [10, 20]


def test_multiple_seeds_differ(game: TrucoGame):
    s1 = game.reset(seed=0)
    s2 = game.reset(seed=1)
    assert s1.manos != s2.manos or s1.muestra != s2.muestra


def test_same_seed_same_deal_on_a_reused_game(game: TrucoGame):
    """R-01 / #25: the deck is not shuffled in place across resets."""
    first = game.reset(seed=123)
    game.reset(seed=999)
    again = game.reset(seed=123)
    assert first.manos == again.manos and first.muestra == again.muestra
    assert TrucoGame().reset(seed=123).manos == first.manos


def test_mano_plays_first(game: TrucoGame):
    state = game.reset(deal=_deal({}), mano=4)
    assert state.phase == Phase.PLAY
    assert state.current_player == 4
    assert state.order == [4, 5, 0, 1, 2, 3]


@pytest.mark.parametrize("ley", [False, True])
def test_random_hands_always_terminate(ley: bool):
    """Liveness (#7, #9): every hand ends; legal actions are never empty or repeated."""
    game = TrucoGame(rules=Rules(ley_de_juego=ley))
    rng = random.Random(7)
    for i in range(3000):
        seats = None if i % 3 else [i % 6, (i + 3) % 6]
        state = game.reset(
            seed=i,
            scores=[rng.randrange(40), rng.randrange(40)],
            mano=seats[0] if seats else rng.randrange(6),
            seats=seats,
            falta_cap=10 if seats else None,
        )
        for _ in range(200):
            if state.phase == Phase.DONE:
                break
            legal = game.legal_actions(state)
            assert legal and len(set(legal)) == len(legal)
            game.apply_action(state, rng.choice(legal))
        assert state.phase == Phase.DONE
        assert min(state.hand_pts) >= 0


def test_scores_absorb_hand_pts(game: TrucoGame):
    state = game.reset(seed=5, scores=[3, 4])
    _accept_everything(game, state)
    assert state.scores == [3 + state.hand_pts[0], 4 + state.hand_pts[1]]


# ──────────────────────────────────────────────────────────────────────────
# Tricks
# ──────────────────────────────────────────────────────────────────────────


def test_two_pardas_then_b_wins_trick_three(game: TrucoGame):
    """A-07 / #11 through the engine: mano-a-mano, both pardas, B takes the third."""
    deal = _deal(
        {
            0: [(ESP, 3), (ESP, 6), (BAS, 4)],
            3: [(BAS, 3), (BAS, 6), (ORO, 5)],
        }
    )
    state = game.reset(deal=deal, mano=0, seats=[0, 3])
    for card in [(ESP, 3), (BAS, 3), (ESP, 6), (BAS, 6), (BAS, 4), (ORO, 5)]:
        game.apply_action(state, card_to_action(*card))
    assert state.trick_winners == [-1, -1, 1]
    assert state.hand_pts == [0, 1]


def test_parda_lead_goes_to_mano(game: TrucoGame):
    """S2 Art 57: after a parda the most-mano player leads."""
    deal = _deal({0: [(ESP, 3), (ORO, 4), (BAS, 6)], 3: [(BAS, 3), (ORO, 6), (ESP, 4)]})
    state = game.reset(deal=deal, mano=0, seats=[0, 3])
    game.apply_action(state, card_to_action(ESP, 3))
    game.apply_action(state, card_to_action(BAS, 3))
    assert state.trick_winners[0] == -1
    assert state.current_player == 0


# ──────────────────────────────────────────────────────────────────────────
# Truco
# ──────────────────────────────────────────────────────────────────────────


def test_vale_cuatro_is_not_an_answer_to_truco(game: TrucoGame):
    """A-03 / #8."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.TRUCO)
    legal = game.legal_actions(state)
    assert Action.RETRUCO in legal
    assert Action.VALE_CUATRO not in legal
    game.apply_action(state, Action.RETRUCO)
    assert Action.VALE_CUATRO in game.legal_actions(state)


@pytest.mark.parametrize(
    ("raises", "pts"),
    [([Action.TRUCO], 1), ([Action.TRUCO, Action.RETRUCO], 2), (list(Action)[10:13], 3)],
)
def test_no_quiero_pays_the_accepted_value(game: TrucoGame, raises: list[Action], pts: int):
    state = game.reset(deal=_deal({}))
    for a in raises:
        game.apply_action(state, a)
    caller_team = state.truco_team
    game.apply_action(state, Action.FOLD)
    assert state.phase == Phase.DONE
    assert state.hand_pts[caller_team] == pts


def test_truco_can_be_called_mid_hand_and_raised_later_by_accepting_side(game: TrucoGame):
    """A-12 / #20: truco in trick 2, retruco by the side that said quiero in trick 3."""
    state = game.reset(deal=_deal({}), mano=0)
    for _ in range(6):
        _play_card(game, state)
    assert state.trick_num == 1 and state.phase == Phase.PLAY
    caller = state.current_player
    assert Action.TRUCO in game.legal_actions(state)
    game.apply_action(state, Action.TRUCO)
    responder = state.current_player
    assert team_of(responder) != team_of(caller)
    game.apply_action(state, Action.QUIERO)
    assert state.current_player == caller and state.truco_level == 2
    assert Action.RETRUCO not in game.legal_actions(state)  # the caller's side may not raise
    while state.phase == Phase.PLAY and team_of(state.current_player) == team_of(caller):
        _play_card(game, state)
    assert state.phase == Phase.PLAY  # the accepting side's turn, still in the hand
    assert Action.RETRUCO in game.legal_actions(state)


def test_any_team_member_may_call_truco(game: TrucoGame):
    """A-13 / #21: every player can call on their own turn; the first rival to the
    caller's right answers."""
    state = game.reset(deal=_deal({}), mano=0)
    _play_card(game, state)  # seat 0
    _play_card(game, state)  # seat 1
    assert state.current_player == 2
    game.apply_action(state, Action.TRUCO)
    assert state.current_player == 3


def test_mano_a_mano_hand_only_seats_the_pair(game: TrucoGame):
    state = game.reset(deal=_deal({}), mano=2, seats=[2, 5], falta_cap=10)
    assert state.order == [2, 5]
    assert state.in_play == [False, False, True, False, False, True]
    _accept_everything(game, state)
    assert sum(state.hand_pts) >= 1


# ──────────────────────────────────────────────────────────────────────────
# Envido
# ──────────────────────────────────────────────────────────────────────────


def test_envido_called_in_turn_before_first_card(game: TrucoGame):
    state = game.reset(deal=_deal({}))
    assert Action.ENVIDO in game.legal_actions(state)
    _play_card(game, state)  # seat 0 played: may not envido any more
    for _ in range(5):
        _play_card(game, state)
    assert not any(a in ENVIDO_CALLS for a in game.legal_actions(state))


def test_player_who_said_truco_cannot_envido(game: TrucoGame):
    """S2 Art 22c."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.TRUCO)
    game.apply_action(state, Action.QUIERO)
    assert state.current_player == 0
    assert Action.ENVIDO not in game.legal_actions(state)


def test_envido_va_primero(game: TrucoGame):
    """S2 Art 60: the side answering a truco may first call envido."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.TRUCO)
    responder = state.current_player
    assert Action.ENVIDO in game.legal_actions(state)
    game.apply_action(state, Action.ENVIDO)
    assert state.phase == Phase.ENVIDO
    game.apply_action(state, Action.QUIERO)
    assert state.phase == Phase.TRUCO and state.current_player == responder
    assert Action.ENVIDO not in game.legal_actions(state)


def test_envido_then_truco_in_one_turn(game: TrucoGame):
    """A-15 / #23 (S2 Art 69): envido and truco together = envido first, then truco."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.ENVIDO)
    game.apply_action(state, Action.QUIERO)
    assert state.current_player == 0
    game.apply_action(state, Action.TRUCO)
    assert state.phase == Phase.TRUCO


@pytest.mark.parametrize(
    ("calls", "answer", "expected"),
    [
        ([Action.ENVIDO], Action.FOLD, 1),
        ([Action.ENVIDO], Action.QUIERO, 2),
        ([Action.ENVIDO, Action.ENVIDO], Action.FOLD, 2),
        ([Action.ENVIDO, Action.ENVIDO], Action.QUIERO, 4),
        ([Action.ENVIDO, Action.REAL_ENVIDO], Action.QUIERO, 5),
        ([Action.ENVIDO, Action.REAL_ENVIDO], Action.FOLD, 2),
        ([Action.DOS_REAL_ENVIDO], Action.QUIERO, 6),
    ],
)
def test_envido_payouts(game: TrucoGame, calls: list[Action], answer: Action, expected: int):
    """docs/rules.md §3.3 / §7: sums; a declined raise pays what was accepted."""
    state = game.reset(deal=_scripted(envido=[33, 20, 0, 0, 0, 0]))
    for a in calls:
        game.apply_action(state, a)
    last_caller = state.envite_team
    game.apply_action(state, answer)
    winner = last_caller if answer == Action.FOLD else 0
    assert state.hand_pts[winner] == expected
    assert state.hand_pts[1 - winner] == 0


def test_raise_must_be_at_least_the_call(game: TrucoGame):
    """S2 Art 35: no envido (2) over a real envido (3)."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.REAL_ENVIDO)
    legal = game.legal_actions(state)
    assert Action.ENVIDO not in legal
    assert Action.REAL_ENVIDO in legal


def test_envido_total_capped_at_falta_and_chain_ends(game: TrucoGame):
    """A-04 / #9: scores [38, 30] → falta 2; nothing can be raised past it."""
    state = game.reset(deal=_deal({}), scores=[38, 30])
    assert state.falta == 2
    game.apply_action(state, Action.ENVIDO)
    assert state.envite_total == 2
    assert game.legal_actions(state) == [Action.QUIERO, Action.FOLD]


def test_envido_chain_bounded_at_any_score(game: TrucoGame):
    for scores in ([0, 0], [20, 35], [39, 0]):
        state = game.reset(deal=_deal({}), scores=scores)
        game.apply_action(state, Action.ENVIDO)
        for _ in range(40):
            raises = [a for a in game.legal_actions(state) if a in ENVIDO_CALLS]
            if not raises:
                break
            game.apply_action(state, raises[0])
            assert state.envite_total <= state.falta
        assert game.legal_actions(state) == [Action.QUIERO, Action.FOLD]


def test_hasta_igualar_levels_the_scores(game: TrucoGame):
    state = game.reset(deal=_scripted(envido=[0, 33, 0, 0, 0, 0]), scores=[30, 22], mano=1)
    assert Action.HASTA_IGUALAR in game.legal_actions(state)  # team B trails by 8
    game.apply_action(state, Action.HASTA_IGUALAR)
    game.apply_action(state, Action.QUIERO)
    assert state.hand_pts == [0, 8]


def test_falta_envido_pays_leaders_shortfall(game: TrucoGame):
    state = game.reset(deal=_scripted(envido=[0, 33, 0, 0, 0, 0]), scores=[30, 10], mano=1)
    game.apply_action(state, Action.FALTA_ENVIDO)
    game.apply_action(state, Action.QUIERO)
    assert state.hand_pts == [0, 10]


def test_envido_tie_goes_by_declaration_procedure(game: TrucoGame):
    """A-05 / #10: [6, 33, 33, 7, 5, 28] → B declared 33 first, B is paid."""
    state = game.reset(deal=_scripted(envido=[6, 33, 33, 7, 5, 28]))
    game.apply_action(state, Action.ENVIDO)
    game.apply_action(state, Action.QUIERO)
    assert state.hand_pts == [0, 2]


def test_envido_reaching_the_chico_ends_the_hand(game: TrucoGame):
    state = game.reset(deal=_scripted(envido=[33, 0, 0, 0, 0, 0]), scores=[38, 0])
    game.apply_action(state, Action.ENVIDO)
    game.apply_action(state, Action.QUIERO)
    assert state.phase == Phase.DONE and state.scores == [40, 0]


# ──────────────────────────────────────────────────────────────────────────
# Flor
# ──────────────────────────────────────────────────────────────────────────


def test_one_sided_flor_pays_three_each_and_voids_envido(game: TrucoGame):
    state = game.reset(deal=_scripted(flor={0: 30, 2: 25}))
    assert state.hand_pts == [6, 0]
    assert state.phase == Phase.PLAY
    assert not any(a in ENVIDO_CALLS for a in game.legal_actions(state))


def test_flor_contest_cannot_be_folded_without_a_challenge(game: TrucoGame):
    """A-09 / #18: a plain flor is compared, not declined."""
    state = game.reset(deal=_deal({0: FLOR_ESP, 1: FLOR_BAS}))
    assert state.phase == Phase.FLOR
    assert Action.FOLD not in game.legal_actions(state)
    game.apply_action(state, Action.FLOR_PASS)
    assert Action.FOLD not in game.legal_actions(state)
    game.apply_action(state, Action.FLOR_PASS)
    assert state.hand_pts == [3, 0]  # 34 beats 28
    assert state.phase == Phase.PLAY


def test_contested_flor_pays_every_flor_of_the_winning_side(game: TrucoGame):
    """A-08 / #17: A holds two flors and wins → 6, not a flat 3."""
    state = game.reset(deal=_scripted(flor={0: 35, 4: 38, 5: 28}))
    game.apply_action(state, Action.FLOR_PASS)
    game.apply_action(state, Action.FLOR_PASS)
    assert state.hand_pts == [6, 0]


def test_con_flor_envido_pays_tantos_plus_winner_flors(game: TrucoGame):
    state = game.reset(deal=_scripted(flor={0: 35, 1: 30}))
    game.apply_action(state, Action.ENVIDO)  # «con flor envido»
    game.apply_action(state, Action.QUIERO)
    assert state.hand_pts == [2 + 3, 0]  # = S3's «5 tantos» with one flor each


def test_declined_con_flor_pays_caller_own_flors(game: TrucoGame):
    state = game.reset(deal=_scripted(flor={0: 20, 2: 21, 1: 40}))
    game.apply_action(state, Action.ENVIDO)
    game.apply_action(state, Action.FOLD)
    assert state.hand_pts == [6, 0]


def test_full_envido_ladder_available_con_flor(game: TrucoGame):
    """A-10 / #19 (S2 Art 27, 37): real envido, falta envido, contra flor al resto."""
    state = game.reset(deal=_deal({0: FLOR_ESP, 1: FLOR_BAS}))
    legal = game.legal_actions(state)
    for a in (
        Action.ENVIDO,
        Action.REAL_ENVIDO,
        Action.FALTA_ENVIDO,
        Action.CONTRA_FLOR_AL_RESTO,
    ):
        assert a in legal


def test_contra_flor_al_resto_is_terminal(game: TrucoGame):
    """A-01 / #7: nothing re-raises contra flor al resto, at any score."""
    for scores in ([0, 0], [37, 0]):
        state = game.reset(deal=_deal({0: FLOR_ESP, 1: FLOR_BAS}), scores=scores)
        game.apply_action(state, Action.CONTRA_FLOR_AL_RESTO)
        assert game.legal_actions(state) == [Action.QUIERO, Action.FOLD]


def test_flor_ladder_never_goes_backwards(game: TrucoGame):
    """A-01 / #7: stakes only rise; the old 5 → 3 → 5 cycle is gone."""
    state = game.reset(deal=_deal({0: FLOR_ESP, 1: FLOR_BAS}), scores=[37, 0])
    game.apply_action(state, Action.ENVIDO)
    totals = [state.envite_total]
    while state.phase == Phase.FLOR:
        raises = [a for a in game.legal_actions(state) if a not in (Action.QUIERO, Action.FOLD)]
        if not raises:
            break
        game.apply_action(state, raises[0])
        totals.append(state.envite_total)
    assert totals == sorted(totals) and len(totals) <= 4


@pytest.mark.parametrize("bidder_seat", [0, 1])
def test_contra_flor_al_resto_is_the_leaders_shortfall(game: TrucoGame, bidder_seat: int):
    """A-02 / #15: same score line → same resto, whoever bids; winner also takes
    both sides' flors (S2 Art 31)."""
    flor = {0: 35, 1: 30}
    state = game.reset(deal=_scripted(flor=flor), scores=[30, 10], mano=bidder_seat)
    game.apply_action(state, Action.CONTRA_FLOR_AL_RESTO)
    assert state.envite_total == 10
    game.apply_action(state, Action.QUIERO)
    assert state.hand_pts == [10 + 6, 0]


def test_flor_tie_goes_by_declaration_procedure(game: TrucoGame):
    """A-06 / #16: A 30 (seat 0), A 33 (seat 2), B 33 (seat 3) → B declares 33 first."""
    state = game.reset(deal=_scripted(flor={0: 30, 2: 33, 3: 33}))
    game.apply_action(state, Action.FLOR_PASS)
    game.apply_action(state, Action.FLOR_PASS)
    assert state.hand_pts == [0, 3]


def test_flor_tie_with_mano_goes_to_mano(game: TrucoGame):
    state = game.reset(deal=_scripted(flor={0: 33, 1: 33}))
    game.apply_action(state, Action.FLOR_PASS)
    game.apply_action(state, Action.FLOR_PASS)
    assert state.hand_pts == [3, 0]


# ──────────────────────────────────────────────────────────────────────────
# Paso / mazo
# ──────────────────────────────────────────────────────────────────────────


def test_mazo_concedes_the_hand(game: TrucoGame):
    """A-11 / #12: going to the mazo hands the rival the hand's value."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.TRUCO)
    game.apply_action(state, Action.QUIERO)
    game.apply_action(state, Action.MAZO)
    assert state.phase == Phase.DONE
    assert state.hand_pts == [0, 2]


def test_paso_leaves_teammates_in_play(game: TrucoGame):
    """A-11 / #12 (S2 Art 88): «paso» takes only that player out."""
    state = game.reset(deal=_deal({}))
    game.apply_action(state, Action.PASO)
    assert not state.in_play[0]
    assert state.phase == Phase.PLAY and state.current_player == 1
    _accept_everything(game, state)
    assert all(0 not in trick for trick in state.tricks)


def test_last_player_of_a_side_has_only_mazo(game: TrucoGame):
    state = game.reset(deal=_deal({}), mano=0, seats=[0, 3])
    legal = game.legal_actions(state)
    assert Action.MAZO in legal and Action.PASO not in legal


# ──────────────────────────────────────────────────────────────────────────
# «A ley de juego» (#23)
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def ley_game() -> TrucoGame:
    return TrucoGame(rules=Rules(ley_de_juego=True))


def test_ley_offered_to_trailing_side_then_the_other(ley_game: TrucoGame):
    state = ley_game.reset(deal=_deal({}), scores=[25, 10])
    assert state.phase == Phase.LEY and team_of(state.current_player) == 1
    ley_game.apply_action(state, Action.LEY_PASS)
    assert state.phase == Phase.LEY and team_of(state.current_player) == 0
    ley_game.apply_action(state, Action.LEY_PASS)
    assert state.phase == Phase.PLAY


def test_ley_falta_and_truco_answered_in_part(ley_game: TrucoGame):
    state = ley_game.reset(deal=_scripted(envido=[33, 0, 0, 0, 0, 0]), scores=[25, 30])
    assert team_of(state.current_player) == 0  # the trailing side
    ley_game.apply_action(state, Action.LEY_FALTA_TRUCO)
    assert Action.LEY_QUIERO_ENVITE in ley_game.legal_actions(state)
    ley_game.apply_action(state, Action.LEY_QUIERO_ENVITE)  # falta yes, truco no
    assert state.phase == Phase.DONE
    assert state.hand_pts == [10 + 1, 0]  # falta 10, then the declined truco's 1


def test_ley_falta_won_by_the_leader_ends_the_chico(ley_game: TrucoGame):
    """S2 Art 80: the leading side winning the envite ends the round and the chico."""
    state = ley_game.reset(deal=_scripted(envido=[0, 33, 0, 0, 0, 0]), scores=[25, 30])
    ley_game.apply_action(state, Action.LEY_FALTA_TRUCO)
    ley_game.apply_action(state, Action.LEY_QUIERO_ENVITE)
    assert state.phase == Phase.DONE
    assert state.hand_pts == [0, 10]


def test_ley_resto_needs_flor_on_both_sides(ley_game: TrucoGame):
    state = ley_game.reset(deal=_scripted(flor={0: 25, 1: 35}), scores=[0, 0])
    ley_game.apply_action(state, Action.LEY_RESTO)
    ley_game.apply_action(state, Action.QUIERO)
    assert state.hand_pts == [0, 40 + 6]
    assert state.phase == Phase.DONE


def test_ley_omitting_the_envite_bars_the_challenger(ley_game: TrucoGame):
    """S2 Art 78: a challenger who left out the falta may not envido this hand."""
    state = ley_game.reset(deal=_deal({}), scores=[0, 0])
    ley_game.apply_action(state, Action.LEY_TRUCO)
    ley_game.apply_action(state, Action.QUIERO)
    assert state.phase == Phase.PLAY and state.truco_level == 2
    assert Action.ENVIDO not in ley_game.legal_actions(state)  # seat 0, team A
    _play_card(ley_game, state)
    assert Action.ENVIDO not in ley_game.legal_actions(state)  # seat 1 said «quiero» (Art 22c)
    _play_card(ley_game, state)
    _play_card(ley_game, state)
    assert state.current_player == 3
    assert Action.ENVIDO in ley_game.legal_actions(state)  # seat 3, team B
