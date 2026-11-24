"""
Probability cheat sheet for the 3v3 game, as quoted in ``docs/become-a-master.md``.

Prints three markdown tables:

1. Piezas: exact hypergeometric odds (who else holds a pieza when you hold none).
2. Envido: Monte Carlo odds that at least one of the three opponents beats your score,
   plus how often your own hand reaches it.
3. Pico a pico: exact odds that your rival holds a pieza, given how many cards earlier
   picos showed and how many of them went face down (piezas go «por abajo»).

Usage:
    uv run python scripts/cheatsheet.py
    uv run python scripts/cheatsheet.py --n 500000 --seed 7
"""

import argparse
import random
from dataclasses import dataclass
from math import comb

from engine.truco import EQUIPO_B, construir_mazo, es_pieza, simular_mano
from log import get_logger

logger = get_logger(__name__)

DECK_SIZE = 40
HAND_SIZE = 3
N_PIEZAS = 5  # 2, 4, 5, 11, 10 of the muestra suit; the 12 stands in when the muestra is one
UNKNOWN_POOL = DECK_SIZE - HAND_SIZE - 1  # cards you can't see: not yours, not the muestra
CARDS_PER_PICO = 2 * HAND_SIZE  # a full mano a mano shows both players' three cards
ME = 0  # seat used for the Monte Carlo tables (team A: seats 0, 2, 4)

ENVIDO_THRESHOLDS = range(25, 34)
OWN_ENVIDO_MARKS = (33, 30, 27)
PICO_POSITIONS = (1, 2, 3)
MAX_TAPADAS = 2


@dataclass(frozen=True, slots=True)
class EnvidoOdds:
    beaten: dict[int, float]  # X -> P(at least one opponent has more than X)
    own_at_least: dict[int, float]  # X -> P(my envido >= X)
    n: int


def p_me_pieza() -> float:
    """P(my three cards include at least one pieza), before seeing anything else."""
    pool = DECK_SIZE - 1  # every card but the muestra
    return 1 - comb(pool - N_PIEZAS, HAND_SIZE) / comb(pool, HAND_SIZE)


def p_any_pieza(n_players: int) -> float:
    """P(at least one of `n_players` other players holds a pieza | I hold none)."""
    cards = n_players * HAND_SIZE
    return 1 - comb(UNKNOWN_POOL - N_PIEZAS, cards) / comb(UNKNOWN_POOL, cards)


def p_rival_pieza_pico(seen: int, tapadas: int) -> float:
    """
    P(my pico rival holds a pieza | I hold none), after earlier picos showed `seen`
    cards, `tapadas` of them face down (= piezas, identity unknown).
    """
    pool = UNKNOWN_POOL - seen
    piezas_left = N_PIEZAS - tapadas
    return 1 - comb(pool - piezas_left, HAND_SIZE) / comb(pool, HAND_SIZE)


def envido_odds(n: int, seed: int | None) -> EnvidoOdds:
    """Monte Carlo over full 6-player deals, from seat ME's point of view."""
    rng = random.Random(seed)
    mazo = construir_mazo()
    beaten = dict.fromkeys(ENVIDO_THRESHOLDS, 0)
    own = dict.fromkeys(OWN_ENVIDO_MARKS, 0)
    for _ in range(n):
        r = simular_mano(mazo, rng)
        envidos = r["envidos"]
        best_opp = max(envidos[i] for i in EQUIPO_B)
        for x in beaten:
            if best_opp > x:
                beaten[x] += 1
        for x in own:
            if envidos[ME] >= x:
                own[x] += 1
    return EnvidoOdds(
        beaten={x: c / n for x, c in beaten.items()},
        own_at_least={x: c / n for x, c in own.items()},
        n=n,
    )


def p_pieza_mc(n: int, seed: int | None) -> float:
    """Monte Carlo check of `p_me_pieza` against the engine's own `es_pieza`."""
    rng = random.Random(seed)
    mazo = construir_mazo()
    hits = 0
    for _ in range(n):
        r = simular_mano(mazo, rng)
        palo_m, num_m = r["muestra"]
        if any(es_pieza(p, num, palo_m, num_m) for p, num in r["manos"][ME]):
            hits += 1
    return hits / n


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


def render(odds: EnvidoOdds) -> str:
    lines = [
        "### Piezas (exact)",
        "",
        "| Situation | Probability |",
        "| --- | --- |",
        f"| You hold a pieza | {_pct(p_me_pieza())} |",
        f"| You hold none: a given other player has one | {_pct(p_any_pieza(1))} |",
        f"| You hold none: at least one of your 2 partners has one | {_pct(p_any_pieza(2))} |",
        f"| You hold none: at least one of the 3 opponents has one | {_pct(p_any_pieza(3))} |",
        "",
        f"### Envido (Monte Carlo, {odds.n:,} deals)",
        "",
        "| Your envido | P(an opponent has more) |",
        "| --- | --- |",
    ]
    lines += [f"| {x} | {_pct(p)} |" for x, p in odds.beaten.items()]
    lines += [
        "",
        "| Your hand reaches | How often |",
        "| --- | --- |",
    ]
    lines += [f"| {x} or more | {_pct(p)} |" for x, p in odds.own_at_least.items()]
    header = " | ".join(f"{t} tapada{'s' if t != 1 else ''}" for t in range(MAX_TAPADAS + 1))
    lines += [
        "",
        "### Pico a pico (exact, you hold no pieza)",
        "",
        f"| Your pico | Cards shown before | {header} |",
        "| --- | --- |" + " --- |" * (MAX_TAPADAS + 1),
    ]
    for pos in PICO_POSITIONS:
        seen = (pos - 1) * CARDS_PER_PICO
        cells = [
            _pct(p_rival_pieza_pico(seen, t)) if t <= seen else "—" for t in range(MAX_TAPADAS + 1)
        ]
        lines.append(f"| {pos} | {seen} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--n", type=int, default=300_000, help="Monte Carlo deals")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logger.info("Simulating %d deals (seed %d)", args.n, args.seed)
    odds = envido_odds(args.n, args.seed)
    print(render(odds))


if __name__ == "__main__":
    main()
