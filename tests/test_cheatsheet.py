"""The 3v3 probability cheat sheet (scripts/cheatsheet.py) quoted in docs/become-a-master.md."""

from math import comb

import pytest

from scripts.cheatsheet import (
    EnvidoOdds,
    envido_odds,
    p_any_pieza,
    p_me_pieza,
    p_pieza_mc,
    p_rival_pieza_pico,
    render,
)


def test_exact_pieza_odds_match_hand_computed_values() -> None:
    assert p_me_pieza() == pytest.approx(1 - comb(34, 3) / comb(39, 3))
    assert p_any_pieza(1) == pytest.approx(0.370, abs=1e-3)
    assert p_any_pieza(2) == pytest.approx(0.622, abs=1e-3)
    assert p_any_pieza(3) == pytest.approx(0.786, abs=1e-3)


def test_exact_pieza_odds_agree_with_engine_deals() -> None:
    # The formula assumes exactly 5 piezas outside the muestra; the engine's es_pieza
    # (with the 12 standing in for a pieza muestra) must agree.
    assert p_pieza_mc(40_000, seed=1) == pytest.approx(p_me_pieza(), abs=0.01)


def test_pico_first_position_equals_one_v_one() -> None:
    assert p_rival_pieza_pico(seen=0, tapadas=0) == pytest.approx(p_any_pieza(1))


def test_pico_odds_rise_with_clean_cards_and_fall_with_tapadas() -> None:
    assert p_rival_pieza_pico(6, 0) < p_rival_pieza_pico(12, 0)
    assert p_rival_pieza_pico(12, 0) > p_rival_pieza_pico(12, 1) > p_rival_pieza_pico(12, 2)
    assert p_rival_pieza_pico(12, 0) == pytest.approx(0.521, abs=1e-3)


def test_envido_odds_are_monotone() -> None:
    odds = envido_odds(5_000, seed=3)
    beaten = list(odds.beaten.values())
    assert all(a >= b for a, b in zip(beaten, beaten[1:], strict=False))
    own = list(odds.own_at_least.values())  # marks are 33, 30, 27: descending thresholds
    assert all(a <= b for a, b in zip(own, own[1:], strict=False))


def test_render_has_all_three_tables() -> None:
    odds = EnvidoOdds(beaten={30: 0.5}, own_at_least={30: 0.3}, n=10)
    out = render(odds)
    assert "### Piezas" in out
    assert "### Envido" in out
    assert "### Pico a pico" in out
