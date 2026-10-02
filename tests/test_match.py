"""TrucoMatch: chicos, mano rotation, redondilla / pico-a-pico alternation (#22)."""

import random

from engine.actions import Action, is_card_action
from engine.match import MatchState, TrucoMatch
from engine.rules import Rules


def _finish_hand(match: TrucoMatch, ms: MatchState) -> None:
    """Play the current hand out: accept nothing, raise nothing, play cards."""
    hand = ms.hand
    while ms.hand is hand and not match.is_terminal(ms):
        legal = match.legal_actions(ms)
        for a in (Action.FOLD, Action.FLOR_PASS, Action.LEY_PASS):
            if a in legal:
                match.apply_action(ms, a)
                break
        else:
            match.apply_action(ms, next(a for a in legal if is_card_action(a)))


def test_first_round_is_general_then_pico_a_pico():
    match = TrucoMatch()
    ms = match.reset(seed=3, mano=0)
    assert ms.hand.seats == list(range(6)) and not ms.pico
    _finish_hand(match, ms)
    assert ms.pico
    assert ms.round_mano == 1
    assert ms.hand.seats == [1, 4] and ms.hand.mano == 1
    assert ms.hand.falta <= match.rules.pico_falta_cap


def test_pico_round_plays_three_pairs_off_one_deal():
    match = TrucoMatch()
    ms = match.reset(seed=3, mano=0)
    _finish_hand(match, ms)
    assert ms.pico
    deal = ms.deal
    pairs = []
    for _ in range(3):
        pairs.append(tuple(ms.hand.order))
        assert ms.deal is deal
        _finish_hand(match, ms)
    assert pairs == [(1, 4), (2, 5), (3, 0)]
    assert not ms.pico and ms.round_mano == 2 and len(ms.hand.seats) == 6


def test_pico_rounds_only_start_below_half():
    """S2 Art 83: mano-a-mano rounds only while both sides are in the malas."""
    match = TrucoMatch()
    for seed in range(30):
        rng = random.Random(seed)
        ms = match.reset(seed=seed)
        rounds = {"general": 0, "pico": 0}
        while not match.is_terminal(ms):
            hand = ms.hand
            if len(hand.seats) == 6:
                rounds["general"] += 1
            elif hand.mano == ms.round_mano:  # first pair of a pico round
                rounds["pico"] += 1
                assert max(hand.scores) < match.rules.half
            while ms.hand is hand and not match.is_terminal(ms):
                match.apply_action(ms, rng.choice(match.legal_actions(ms)))
        assert rounds["general"] >= 1


def test_redondilla_only_variant():
    match = TrucoMatch(Rules(pico_a_pico=False))
    ms = match.reset(seed=5)
    for _ in range(5):
        _finish_hand(match, ms)
        assert len(ms.hand.seats) == 6


def test_mano_rotates_every_round():
    match = TrucoMatch(Rules(pico_a_pico=False))
    ms = match.reset(seed=6, mano=4)
    manos = [ms.hand.mano]
    for _ in range(3):
        _finish_hand(match, ms)
        manos.append(ms.hand.mano)
    assert manos == [4, 5, 0, 1]


def test_match_ends_at_chico_and_best_of_three():
    for rules in (Rules(), Rules(chicos_to_win=2)):
        match = TrucoMatch(rules)
        rng = random.Random(0)
        ms = match.reset(seed=11)
        while not match.is_terminal(ms):
            match.apply_action(ms, rng.choice(match.legal_actions(ms)))
        assert ms.chicos[ms.winner] == rules.chicos_to_win
        assert ms.chicos[1 - ms.winner] < rules.chicos_to_win


def test_pico_falta_cap_applies_to_falta_and_resto():
    match = TrucoMatch(Rules(pico_falta_cap=6))
    ms = match.reset(seed=3)
    _finish_hand(match, ms)
    assert ms.pico and ms.hand.falta == 6
