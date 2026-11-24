"""Layer 1: exhaustive pure-function comparisons, returning mismatch records."""

from collections.abc import Iterator
from itertools import combinations

from pytruco.pdt.equipo import Equipo
from pytruco.pdt.manojo import Manojo

from engine.card import card_strength
from engine.game_state import Card
from engine.rules import falta
from engine.truco import (
    calcular_envido,
    calcular_flor,
    construir_mazo,
    es_pieza,
    tiene_flor,
)

from .adapter import empty_partida, to_carta

Mismatch = dict[str, object]

DECK: list[Card] = construir_mazo()


def _manojo() -> Manojo:
    from pytruco.pdt.jugador import Jugador

    return Manojo(Jugador("x", Equipo.AZUL))


def deals() -> Iterator[tuple[Card, tuple[Card, ...]]]:
    """Every (muestra, 3-card hand) with the muestra excluded from the hand."""
    for muestra in DECK:
        rest = [c for c in DECK if c != muestra]
        for hand in combinations(rest, 3):
            yield muestra, hand


def pieza_mismatches() -> list[Mismatch]:
    out: list[Mismatch] = []
    for muestra in DECK:
        m = to_carta(muestra)
        for card in DECK:
            ours = es_pieza(*card, *muestra)
            theirs = to_carta(card).es_pieza(m)
            if ours != theirs:
                out.append(
                    {
                        "layer": "pieza",
                        "card": card,
                        "muestra": muestra,
                        "ours": ours,
                        "theirs": theirs,
                    }
                )
    return out


def strength_mismatches() -> list[Mismatch]:
    """Compare the sign of strength(a) - strength(b): the two scales differ."""
    out: list[Mismatch] = []
    for muestra in DECK:
        m = to_carta(muestra)
        rest = [c for c in DECK if c != muestra]
        ours = {c: card_strength(*c, *muestra) for c in rest}
        theirs = {c: to_carta(c).calc_poder(m) for c in rest}
        for a in rest:
            for b in rest:
                if a == b:
                    continue
                so = (ours[a] > ours[b]) - (ours[a] < ours[b])
                st = (theirs[a] > theirs[b]) - (theirs[a] < theirs[b])
                if so != st:
                    out.append(
                        {
                            "layer": "strength",
                            "a": a,
                            "b": b,
                            "muestra": muestra,
                            "ours": so,
                            "theirs": st,
                        }
                    )
    return out


def hand_mismatches() -> list[Mismatch]:
    """Flor detection + score, and envido (only where neither engine sees a flor)."""
    out: list[Mismatch] = []
    mj = _manojo()
    for muestra, hand in deals():
        mj.cartas = [to_carta(c) for c in hand]
        m = to_carta(muestra)
        o_flor = tiene_flor(list(hand), *muestra)
        t_flor, t_tipo = mj.tiene_flor(m)
        if o_flor != t_flor:
            out.append(
                {
                    "layer": "flor_detect",
                    "hand": hand,
                    "muestra": muestra,
                    "ours": o_flor,
                    "theirs": t_flor,
                }
            )
            continue
        if o_flor:
            o_score = calcular_flor(list(hand), *muestra)
            t_score = mj.calc_flor(m)
            if o_score != t_score:
                out.append(
                    {
                        "layer": "flor_score",
                        "hand": hand,
                        "muestra": muestra,
                        "tipo": t_tipo,
                        "ours": o_score,
                        "theirs": t_score,
                    }
                )
        else:
            o_env = calcular_envido(list(hand), *muestra)
            t_env = mj.calcular_envido(m)
            if o_env != t_env:
                out.append(
                    {
                        "layer": "envido",
                        "hand": hand,
                        "muestra": muestra,
                        "ours": o_env,
                        "theirs": t_env,
                    }
                )
    return out


def falta_mismatches(target: int = 40) -> list[Mismatch]:
    """Falta / resto base points over every score pair and winning team."""
    out: list[Mismatch] = []
    for a in range(target):
        for b in range(target):
            ours = falta([a, b], target)
            for winner in (0, 1):
                p = empty_partida((a, b), target)
                theirs = p.calc_pts_falta_envido(Equipo.AZUL if winner == 0 else Equipo.ROJO)
                resto = p.calc_pts_contraflor_al_resto(Equipo.AZUL if winner == 0 else Equipo.ROJO)
                if ours != theirs or ours != resto:
                    out.append(
                        {
                            "layer": "falta",
                            "scores": (a, b),
                            "winner": winner,
                            "target": target,
                            "ours": ours,
                            "theirs": theirs,
                        }
                    )
    return out
