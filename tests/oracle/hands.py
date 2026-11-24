"""Layer 2: replay random legal action sequences in both engines.

Our engine drives. Each chosen action is translated to the pytruco move(s) for the
same seat; pytruco must accept it (``ok``), trick winners must agree, and the
points each side gains in the hand must agree after every step.

Not compared (structural differences, counted in ``Stats.theirs_only`` instead):
the full legal-action sets. pytruco lets any rival answer, its mazo is per player
and not turn-gated, flor must be sung explicitly, and its envite ladder has other
shapes, so the sets differ at nearly every step.

Left out of the driver by construction: DOS/TRES_REAL_ENVIDO and HASTA_IGUALAR
(V-10), the envite ladder played «con flor» and contra flor al resto (V-02), and
«a ley de juego» (V-09). Pico a pico (V-12) is never entered. Deals whose flor
contest includes a flor derecha without a pieza are skipped (D-01 would only
repeat), and scores start at 20-30 so the leader is out of malas (D-02).
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pytruco.pdt.equipo import Equipo
from pytruco.pdt.jugada import (
    CantarFlor,
    GritarReTruco,
    GritarTruco,
    GritarVale4,
    IrseAlMazo,
    ResponderNoQuiero,
    ResponderQuiero,
    TirarCarta,
    TocarEnvido,
    TocarFaltaEnvido,
    TocarRealEnvido,
)
from pytruco.pdt.mano import Resultado
from pytruco.pdt.partida import IJugada, Partida

from engine.actions import Action, action_to_card, is_card_action
from engine.game import TrucoGame, deal_from_seed
from engine.game_state import GameState, team_of
from engine.phases import Phase
from engine.truco import es_pieza

from .adapter import SEAT_IDS, build_partida, to_carta
from .known_diffs import KNOWN_DIFFS, Mismatch

MAX_STEPS = 300
SCORE_RANGE = (20, 30)

# Selection weights: favour card play so hands run long enough to reach every phase.
WEIGHTS = {
    "card": 6.0,
    "envite": 2.0,
    "truco": 2.0,
    "quiero": 3.0,
    "fold": 1.0,
    "paso": 0.4,
    "mazo": 0.2,
    "flor_pass": 1.0,
}


class RecordingGame(TrucoGame):
    """Our engine, additionally logging each resolved trick as (index, winning team)."""

    def __init__(self) -> None:
        super().__init__()
        self.trick_log: list[tuple[int, int]] = []

    def _resolve_trick(self, state: GameState) -> None:
        t = state.trick_num
        super()._resolve_trick(state)
        self.trick_log.append((t, state.trick_winners[t]))


@dataclass(slots=True)
class Stats:
    hands: int = 0
    skipped_deals: int = 0
    cascades: int = 0
    steps: int = 0
    known: Counter[str] = field(default_factory=Counter)
    theirs_only: Counter[str] = field(default_factory=Counter)  # pytruco allows, we do not
    examples: dict[str, Mismatch] = field(default_factory=dict)  # shortest case per known diff


# What pytruco may allow the current player that we may not (counted, never a failure).
THEIRS_PROBES: dict[Action, type] = {
    Action.TRUCO: GritarTruco,
    Action.RETRUCO: GritarReTruco,
    Action.VALE_CUATRO: GritarVale4,
    Action.ENVIDO: TocarEnvido,
    Action.REAL_ENVIDO: TocarRealEnvido,
    Action.FALTA_ENVIDO: TocarFaltaEnvido,
    Action.QUIERO: ResponderQuiero,
    Action.FOLD: ResponderNoQuiero,
}


def _kind(action: Action) -> str:
    if is_card_action(action):
        return "card"
    if action in (Action.TRUCO, Action.RETRUCO, Action.VALE_CUATRO):
        return "truco"
    if action in (Action.ENVIDO, Action.REAL_ENVIDO, Action.FALTA_ENVIDO):
        return "envite"
    return {
        Action.QUIERO: "quiero",
        Action.FOLD: "fold",
        Action.PASO: "paso",
        Action.MAZO: "mazo",
        Action.FLOR_PASS: "flor_pass",
    }.get(action, "untranslatable")


def to_jugadas(action: Action, state: GameState) -> list[IJugada] | None:
    """pytruco moves equivalent to ``action`` by the current player, or None."""
    sid = SEAT_IDS[state.current_player]
    if is_card_action(action):
        return [TirarCarta(sid, to_carta(action_to_card(action)))]
    simple: dict[Action, type] = {
        Action.ENVIDO: TocarEnvido,
        Action.REAL_ENVIDO: TocarRealEnvido,
        Action.FALTA_ENVIDO: TocarFaltaEnvido,
        Action.TRUCO: GritarTruco,
        Action.RETRUCO: GritarReTruco,
        Action.VALE_CUATRO: GritarVale4,
        Action.QUIERO: ResponderQuiero,
        Action.FOLD: ResponderNoQuiero,
        Action.PASO: IrseAlMazo,
    }
    if action in simple:
        return [simple[action](sid)]
    if action == Action.MAZO:  # our mazo takes the whole side out
        team = team_of(state.current_player)
        if any(
            state.in_play[s] and team_of(s) == team and not state.cards_in_hand[s]
            for s in state.order
        ):
            return None  # pytruco: a player who threw all three cards cannot go to the mazo
        # the current player goes last: pytruco scores the trick as soon as everyone
        # still in play has thrown, which a teammate's later mazo would trigger
        seats = [s for s in state.order if state.in_play[s] and team_of(s) == team]
        seats.sort(key=lambda s: s == state.current_player)
        return [IrseAlMazo(SEAT_IDS[s]) for s in seats]
    return None


def _equipo_team(e: Equipo) -> int:
    return 0 if e == Equipo.AZUL else 1


def _their_tricks(manos: list[Any]) -> list[tuple[int, int]]:
    out = []
    for i, m in enumerate(manos):
        r = m.resultado
        if r is None or r == Resultado.INDETERMINADO:
            continue
        out.append((i, -1 if r == Resultado.EMPARDADA else (0 if r == Resultado.GANO_AZUL else 1)))
    return out


def _skip_deal(deal: Any) -> bool:
    """A contested flor holding a flor derecha without a pieza would only repeat D-01."""
    sides = {team_of(s) for s, f in enumerate(deal.has_flor) if f}
    if len(sides) < 2:
        return False
    pm, nm = deal.muestra
    return any(
        deal.has_flor[s] and not any(es_pieza(p, n, pm, nm) for p, n in deal.manos[s])
        for s in range(6)
    )


def _tied(state: GameState, values: list[int], seats: list[int]) -> bool:
    """Do the two sides' best figures among ``seats`` tie?"""
    best = [max((values[s] for s in seats if team_of(s) == t), default=-1) for t in (0, 1)]
    return best[0] == best[1]


def _verbose(p: Partida) -> Partida:
    """Turn on pytruco's error messages (only used to explain a rejection)."""
    p.verbose = True
    return p


def _their_pts(p: Partida, base: tuple[int, int]) -> list[int]:
    return [p.puntajes[Equipo.AZUL] - base[0], p.puntajes[Equipo.ROJO] - base[1]]


def play_hand(seed: int, stats: Stats, trace: bool = False) -> Mismatch | None:
    """Replay one random hand in both engines; return the first unexplained diff."""
    rng = random.Random(seed)
    deal = deal_from_seed(seed)
    if _skip_deal(deal):
        stats.skipped_deals += 1
        return None
    scores = (rng.randint(*SCORE_RANGE), rng.randint(*SCORE_RANGE))
    mano = rng.randrange(6)

    game = RecordingGame()
    state = game.reset(deal=deal, scores=list(scores), mano=mano)
    p = build_partida([list(h) for h in deal.manos], deal.muestra, mano, scores)
    stats.hands += 1
    prefix: list[str] = []
    offset = [0, 0]  # their points - ours, rebased after an explained diff
    pre: dict[str, Any] = {}  # our state just before the action under test (set per step)

    def snapshot() -> dict[str, Any]:
        return {
            "pre_phase": state.phase.name,
            "pre_accepted": state.envite_accepted,
            "pre_total": state.envite_total,
            "pre_calls": state.envite_calls,
            "pre_last_amount": state.envite_last_amount,
            "pre_envite_kind": state.envite_kind,
            "pre_truco_level": state.truco_level,
            "pre_trick": state.trick_num,
            "pre_prev_parda": bool(game.trick_log)
            and game.trick_log[-1][1] == -1
            and game.trick_log[-1][0] == state.trick_num - 1,
        }

    def report(layer: str, **detail: Any) -> Mismatch | None:
        m: Mismatch = {"layer": layer, "seed": seed, "prefix": list(prefix), **pre, **detail}
        for d in KNOWN_DIFFS:
            if d.layer == layer and d.matches(m):
                stats.known[d.id] += 1
                best = stats.examples.get(d.id)
                if best is None or len(m["prefix"]) < len(best["prefix"]):
                    stats.examples[d.id] = m
                return None
        return m

    def compare_points(event: str) -> Mismatch | None:
        ours = [state.hand_pts[0], state.hand_pts[1]]
        theirs = _their_pts(p, scores)
        if [t - o for t, o in zip(theirs, ours, strict=True)] == offset:
            return None
        flors = [sum(1 for s in state.flor_holders if team_of(s) == t) for t in (0, 1)]
        m = report(
            "hand_points",
            event=event,
            ours=ours,
            theirs=theirs,
            flors=flors,
            envido_tie=_tied(state, state.envido, [s for s in state.order if state.in_play[s]]),
            flor_tie=_tied(state, state.flor_score, state.flor_holders),
            envidos=list(state.envido),
            flor_scores=list(state.flor_score),
            order=list(state.order),
            in_play=list(state.in_play),
        )
        if m is None:  # explained: rebase and continue
            offset[:] = [t - o for t, o in zip(theirs, ours, strict=True)]
        return m

    # Flor preamble: pytruco needs every holder to sing before the first card.
    for s in state.flor_holders:
        sid = SEAT_IDS[s]
        if state.phase == Phase.FLOR:
            continue  # contested: sung after both sides pass, below
        CantarFlor(sid).hacer(p)
    while state.phase == Phase.FLOR:
        if state.envite_team != -1 or Action.FLOR_PASS not in game.legal_actions(state):
            return None  # envite already in progress: out of scope
        prefix.append("FLOR_PASS")
        game.apply_action(state, Action.FLOR_PASS)
    if deal.has_flor and any(deal.has_flor) and len({team_of(s) for s in state.flor_holders}) == 2:
        for s in state.flor_holders:
            CantarFlor(SEAT_IDS[s]).hacer(p)
    if (m := compare_points("flor")) is not None:
        return m

    for _ in range(MAX_STEPS):
        if state.phase == Phase.DONE:
            break
        legal = game.legal_actions(state)
        me = SEAT_IDS[state.current_player]
        for probe, cls in THEIRS_PROBES.items():
            if probe not in legal and cls(me).ok(p)[1]:
                stats.theirs_only[probe.name] += 1
        usable = [(a, to_jugadas(a, state)) for a in legal]
        usable_ok = [(a, js) for a, js in usable if js is not None]
        if not usable_ok:
            return None
        weights = [WEIGHTS[_kind(a)] for a, _ in usable_ok]
        action, jugadas = rng.choices(usable_ok, weights=weights)[0]
        assert jugadas is not None
        prefix.append(f"{SEAT_IDS[state.current_player]}:{action.name}")
        pre = snapshot()
        manos_ref = p.ronda.manos
        for j in jugadas:
            if not j.ok(p)[1]:
                return report(
                    "reject",
                    event=action.name,
                    move=str(j),
                    ours="legal",
                    theirs="rejected",
                    reason=[e.message.cont for e in j.ok(_verbose(p))[0]],
                    turn=(state.current_player, p.ronda.turno),
                    trick=state.trick_num,
                    truco=(state.truco_level, str(p.ronda.truco.estado)),
                    envite=str(p.ronda.envite.estado),
                )
            j.hacer(p)
        game.apply_action(state, action)
        stats.steps += 1
        if trace:
            print(
                prefix[-1],
                "ours",
                state.hand_pts,
                "theirs",
                _their_pts(p, scores),
                "turn",
                state.current_player,
                p.ronda.turno,
            )
        ended_theirs = p.ronda.manos is not manos_ref or p.terminada()
        if (m := compare_points(action.name)) is not None:
            return m
        if (state.phase == Phase.DONE) != ended_theirs:
            if offset != [0, 0]:  # a payout we already explained pushed pytruco to the target
                stats.cascades += 1
                return None
            return report(
                "hand_end", event=action.name, ours=state.phase == Phase.DONE, theirs=ended_theirs
            )
        if ended_theirs:
            ours_tricks = list(game.trick_log)
            # pytruco also scores a trick left half-played by a fold or mazo: compare
            # only the tricks our engine resolved
            resolved = {i for i, _ in ours_tricks}
            theirs_tricks = [t for t in _their_tricks(manos_ref) if t[0] in resolved]
            if ours_tricks != theirs_tricks:
                return report(
                    "trick_winner", event=action.name, ours=ours_tricks, theirs=theirs_tricks
                )
            break
    return None


def run_seeds(seeds: range) -> tuple[list[Mismatch], Stats]:
    stats = Stats()
    found: list[Mismatch] = []
    for seed in seeds:
        m = play_hand(seed, stats)
        if m is not None:
            found.append(m)
    return found, stats
