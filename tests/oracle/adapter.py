"""Mapping between our engine's encodings and pytruco's.

pytruco is a dev-only dependency: nothing under ``engine/`` may import it.

Encodings:
  - card: ours ``(palo_idx, numero)`` with 0=Espadas 1=Bastos 2=Copas 3=Oros;
    theirs ``Carta(valor, palo)`` with string palos.
  - seat: our seat ``i`` is pytruco manojo ``i`` (players named ``s0..s5``);
    even seats are our team 0 = pytruco ``AZUL``, odd seats team 1 = ``ROJO``.
"""

from functools import cache

from pytruco.pdt.carta import Carta
from pytruco.pdt.equipo import Equipo
from pytruco.pdt.partida import Partida

from engine.game_state import Card

PALO_NAMES = ("espada", "basto", "copa", "oro")  # indexed by our palo idx
N_SEATS = 6
SEAT_IDS = tuple(f"s{i}" for i in range(N_SEATS))


@cache
def to_carta(card: Card) -> Carta:
    """Our ``(palo, numero)`` -> pytruco ``Carta`` (cached: cards are immutable here)."""
    palo, numero = card
    return Carta(numero, PALO_NAMES[palo])


def from_carta(carta: Carta) -> Card:
    return (PALO_NAMES.index(str(carta.palo)), carta.valor)


def team_to_equipo(team: int) -> Equipo:
    return Equipo.AZUL if team == 0 else Equipo.ROJO


def empty_partida(scores: tuple[int, int] = (0, 0), target: int = 40) -> Partida:
    """A 6-player dummy ``Partida`` with no cards dealt (score arithmetic only).

    ``limite_envido=-1`` makes pytruco's envido cap the falta (its default of 4
    would saturate envido where ours does not).
    """
    p = Partida(
        puntuacion=target,
        azules=[SEAT_IDS[i] for i in (0, 2, 4)],
        rojos=[SEAT_IDS[i] for i in (1, 3, 5)],
        dummy=True,
        verbose=False,
        limite_envido=-1,
    )
    p.puntajes[Equipo.AZUL] = scores[0]
    p.puntajes[Equipo.ROJO] = scores[1]
    return p


def build_partida(
    manos: list[list[Card]],
    muestra: Card,
    mano: int = 0,
    scores: tuple[int, int] = (0, 0),
    target: int = 40,
) -> Partida:
    """A 6-player pytruco ``Partida`` holding exactly the given deal.

    The muestra is set before the cards: both setters recache flors, which reads
    the muestra (and a card-less hand).
    """
    p = empty_partida(scores, target)
    p.ronda.reset(mano)
    p.ronda.set_muestra(to_carta(muestra))
    p.ronda.set_cartas([[to_carta(c) for c in hand] for hand in manos])
    return p
