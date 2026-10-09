"""
DeterminizedVonNeumannAgent: the fair (imperfect-information) VonNeumann.

``VonNeumannAgent`` rolls out from a deep copy of the *true* state, so it sees every
seat's real hand. This variant instead **determinizes**: before each rollout it
samples the hidden cards (the other seats' unseen hands; the undealt deck is whatever
is left over) uniformly from the deals consistent with what the acting seat can
observe, then rolls out from that sampled world.

What the acting seat observes, and therefore what a sample must agree with:
  - its own hand, the muestra, and every card already played (with who played it);
  - how many cards each other seat still holds;
  - which seats have flor (``has_flor``): flor is sung automatically in this engine,
    so it is public. A sampled hand is accepted only if it has flor exactly when the
    real one does.

Known limitations (it is "fair but belief-naive"):
  - It does NOT condition on envido / flor / truco *calls* as soft evidence ("he
    called real envido, so he probably holds 2 same-suit cards"). That needs an
    opponent model; samples are uniform over consistent deals, not over likely ones.
  - It does NOT condition on the *outcome* of an envido / flor contest. ``GameState``
    stores no declared tantos (only the resulting ``hand_pts``), so a won or lost
    contest is not used to narrow the sampled hands.
  - Rollout play is still uniformly random (the policy is #42's concern, not this).

The EV cache is kept apart from the legacy agent's: its key is built from the full
public state under its own namespace, and its file format carries a header that the
legacy flat-dict cache lacks, so neither agent can ingest the other's values.
"""

import copy
import dataclasses
import json
import random
from pathlib import Path

from engine.actions import Action
from engine.game_state import Card, GameState
from engine.truco import calcular_envido, calcular_flor, construir_mazo, tiene_flor

from .von_neumann_agent import _AUTOSAVE_EVERY, VonNeumannAgent

CACHE_FORMAT = "vn-determinized-v1"  # file header and key namespace; bump if the key changes
_MAX_DEAL_TRIES = 200_000  # rejection-sampling guard; the true deal is always consistent
_HIDDEN_PER_SEAT = ("manos", "cards_in_hand", "envido", "flor_score")  # other seats' secrets


class DeterminizedVonNeumannAgent(VonNeumannAgent):
    """MC rollout agent that samples the hidden cards before every rollout."""

    name = "von_neumann_determinized"

    def __init__(
        self,
        n_rollouts: int = 20,
        seed: int | None = None,
        cache_path: Path | None = None,
    ):
        super().__init__(n_rollouts=n_rollouts, seed=seed, cache_path=cache_path)
        # Own stream, so sampling never shifts the rollout choosers' draws.
        self._det_rng = random.Random(None if seed is None else seed + 1_000_003)

    def save_cache(self) -> None:
        """Persist the EV cache (with its format header). No-op if cache_path is None."""
        path = self._cfg.cache_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"format": CACHE_FORMAT, "ev": self._cache}, f)
        self._new_entries = 0

    def _load_cache(self) -> dict[str, float]:
        path = self._cfg.cache_path
        if path is None or not path.exists():
            return {}
        with open(path) as f:
            blob = json.load(f)
        if not isinstance(blob, dict) or blob.get("format") != CACHE_FORMAT:
            raise ValueError(
                f"{path} is not a {CACHE_FORMAT} cache (a legacy VonNeumannAgent cache holds "
                "perfect-information EVs and must not be reused here)"
            )
        ev: dict[str, float] = blob["ev"]
        return ev

    def _estimate_ev(self, state: GameState, action: Action, player_idx: int) -> float:
        key = _fair_state_key(state, player_idx, action)
        if key in self._cache:
            return self._cache[key]

        total = 0.0
        for _ in range(self._cfg.n_rollouts):
            s = determinize(state, player_idx, self._det_rng)
            self._game.apply_action(s, action)
            total += self._run_rollout(s, player_idx)
        ev = total / self._cfg.n_rollouts

        self._cache[key] = ev
        self._new_entries += 1
        if self._new_entries >= _AUTOSAVE_EVERY:
            self.save_cache()
        return ev


def _played_by(state: GameState) -> dict[int, list[Card]]:
    """Cards each seat has already played this hand (public)."""
    played: dict[int, list[Card]] = {s: [] for s in range(len(state.cards_in_hand))}
    for trick in state.tricks:
        for seat, card in trick.items():
            played[seat].append(card)
    return played


def draw_consistent_hands(
    state: GameState, player_idx: int, rng: random.Random
) -> tuple[dict[int, list[Card]], int]:
    """Sample the other seats' remaining cards; return them and the number of tries.

    Joint rejection sampling: shuffle the unseen cards, deal each other seat as many
    as it still holds, and accept only if every seated seat's hand (played + dealt)
    has flor exactly when ``state.has_flor`` says it does. Accepted draws are uniform
    over the deals consistent with the public information.
    """
    played = _played_by(state)
    visible = {*state.cards_in_hand[player_idx], state.muestra}
    for cards in played.values():
        visible.update(cards)
    pool = [c for c in construir_mazo() if c not in visible]
    others = [s for s in range(len(state.cards_in_hand)) if s != player_idx]
    counts = {s: len(state.cards_in_hand[s]) for s in others}
    pm, nm = state.muestra

    for tries in range(1, _MAX_DEAL_TRIES + 1):
        rng.shuffle(pool)
        hands: dict[int, list[Card]] = {}
        i = 0
        for s in others:
            hands[s] = pool[i : i + counts[s]]
            i += counts[s]
        if all(
            tiene_flor(played[s] + hands[s], pm, nm) == state.has_flor[s]
            for s in others
            if s in state.seats
        ):
            return hands, tries
    raise RuntimeError(
        f"no deal consistent with the public state after {_MAX_DEAL_TRIES} tries "
        f"(player {player_idx}, has_flor={state.has_flor})"
    )


def determinize(state: GameState, player_idx: int, rng: random.Random) -> GameState:
    """A copy of ``state`` in which every other seat's hidden cards are resampled.

    ``state`` is not modified. Everything player ``player_idx`` can observe is preserved;
    the other seats' remaining cards, and the envido / flor scores derived from their
    full hands, are replaced by a sample consistent with the public information.
    """
    hands, _ = draw_consistent_hands(state, player_idx, rng)
    played = _played_by(state)
    s = copy.deepcopy(state)
    pm, nm = state.muestra
    for seat, dealt in hands.items():
        full = played[seat] + dealt
        s.cards_in_hand[seat] = list(dealt)
        s.manos[seat] = full
        s.envido[seat] = calcular_envido(full, pm, nm)
        s.flor_score[seat] = calcular_flor(full, pm, nm) if tiene_flor(full, pm, nm) else 0
    return s


def _fair_state_key(state: GameState, player_idx: int, action: Action) -> str:
    """Cache key over the *whole* public state, as seen from ``player_idx``.

    Every ``GameState`` field is included (so muestra, hand_pts, who-played-which card,
    the ley / envite / truco bookkeeping, seats, ... all distinguish states), except the
    other seats' secrets (``_HIDDEN_PER_SEAT``), of which only the player's own entry is
    kept. Two states that differ only in a rival's hidden hand therefore share a key.
    """
    parts: dict[str, object] = {}
    for f in dataclasses.fields(state):
        value = getattr(state, f.name)
        parts[f.name] = value[player_idx] if f.name in _HIDDEN_PER_SEAT else value
    parts["cards_in_hand"] = sorted(state.cards_in_hand[player_idx])
    return json.dumps(
        [CACHE_FORMAT, player_idx, int(action), parts],
        separators=(",", ":"),
        sort_keys=True,
    )
