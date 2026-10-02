"""Pure rule functions (engine/rules.py) against docs/rules.md."""

import itertools

import pytest

from engine.rules import capped_total, declaration_winner, falta, hand_winner, turn_order

A, B, P = 0, 1, -1  # team A, team B, parda


def _spec_hand_winner(w: tuple[int, ...], mano_team: int) -> int:
    """docs/rules.md §6 table (S1 Art 41; S2 Art 59; S3 L70–81)."""
    w0, w1, w2 = w
    if w0 != P:
        if w1 in (w0, P):
            return w0
        return w2 if w2 != P else w0
    if w1 != P:
        return w1
    return w2 if w2 != P else mano_team


@pytest.mark.parametrize("mano_team", [A, B])
def test_hand_winner_matches_spec_for_all_27_sequences(mano_team: int):
    for w in itertools.product((A, B, P), repeat=3):
        # The engine asks after every trick; the first non-None answer is the winner.
        winner = next(
            r for t in range(1, 4) if (r := hand_winner(list(w[:t]), mano_team)) is not None
        )
        assert winner == _spec_hand_winner(w, mano_team), w


def test_two_pardas_then_b_wins_goes_to_b():
    """A-07 / #11: [parda, parda, B] is B's hand, not mano's."""
    assert hand_winner([P, P, B], mano_team=A) == B


def test_hand_undecided_after_split_first_two_tricks():
    assert hand_winner([A], A) is None
    assert hand_winner([A, B], A) is None
    assert hand_winner([P, P], A) is None


def test_turn_order_runs_right_from_mano():
    assert turn_order(4, range(6)) == [4, 5, 0, 1, 2, 3]
    assert turn_order(3, [0, 3]) == [3, 0]


def test_falta_is_leaders_shortfall_whoever_asks():
    """A-02 / #15: the falta/resto depends only on the leader's score."""
    assert falta([30, 10], 40) == 10
    assert falta([10, 30], 40) == 10
    assert falta([5, 5], 40, cap=10) == 10  # mano-a-mano cap (S2 Art 86)


class TestDeclarationProcedure:
    """S2 Art 39–44: mano declares; a rival declares only to beat; ties don't beat."""

    def test_strictly_higher_figure_wins(self):
        assert declaration_winner({0: 20, 1: 33, 2: 25, 3: 1, 4: 0, 5: 2}, range(6)) == B

    def test_tie_with_mano_goes_to_mano(self):
        assert declaration_winner({0: 30, 1: 30}, [0, 1]) == A

    def test_tie_goes_to_first_declarer_of_figure_not_always_team_a(self):
        """A-05 / #10: envidos [6, 33, 33, 7, 5, 28] → B declares 33 first."""
        values = dict(enumerate([6, 33, 33, 7, 5, 28]))
        assert declaration_winner(values, range(6)) == B

    def test_rules_md_example_not_lowest_seat(self):
        """docs/rules.md §3.5: A 30, B 20, A 33, B 33 → B (A's 33 never speaks)."""
        assert declaration_winner({0: 30, 1: 20, 2: 33, 3: 33}, range(4)) == B

    def test_order_starts_at_mano(self):
        # mano is seat 3 (team B): B declares first and keeps the tie
        assert declaration_winner({3: 28, 4: 28}, turn_order(3, range(6))) == B

    def test_only_listed_seats_declare(self):
        # flor contest: only flor holders declare (S2 Art 40)
        assert declaration_winner({2: 33, 5: 33}, range(6)) == A


class TestEnviteCap:
    """S2 Art 36."""

    def test_first_call_within_falta(self):
        assert capped_total(0, 3, 0, limit=10, first=True) == 3

    def test_first_call_beyond_falta_counts_two(self):
        assert capped_total(0, 3, 0, limit=1, first=True) == 2

    def test_raise_within_falta_sums(self):
        assert capped_total(2, 3, 2, limit=10, first=False) == 5

    def test_raise_beyond_falta_worth_preceding_or_falta(self):
        assert capped_total(4, 3, 2, limit=6, first=False) == 6
        assert capped_total(4, 9, 2, limit=7, first=False) == 6  # preceding (2) fits
