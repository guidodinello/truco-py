"""DeterminizedVonNeumannAgent: it must never read hidden information (see issue #50)."""

import copy
import dataclasses
import json
import random
from pathlib import Path

import pytest

from agents.determinized_von_neumann_agent import (
    _HIDDEN_PER_SEAT,
    _MAX_DEAL_TRIES,
    CACHE_FORMAT,
    DeterminizedVonNeumannAgent,
    _fair_state_key,
    _is_consistent,
    _played_by,
    determinize,
    draw_consistent_hands,
)
from agents.von_neumann_agent import OmniscientVonNeumannAgent
from engine.game import TrucoGame, make_deal
from engine.game_state import Card, GameState
from engine.phases import Phase
from engine.rules import Rules
from engine.truco import construir_mazo, tiene_flor
from scripts import benchmark, league_010

MUESTRA: Card = (3, 7)
ME = [(0, 1), (1, 7), (2, 3)]  # seat 0: identical in both worlds, no flor
# The other five seats' hands: world A holds strong cards, world B weak ones. Nobody has flor.
STRONG = [
    [(1, 1), (0, 7), (3, 2)],
    [(3, 4), (0, 3), (2, 2)],
    [(1, 3), (2, 1), (0, 2)],
    [(3, 5), (1, 2), (0, 10)],
    [(2, 12), (1, 10), (3, 11)],
]
WEAK = [
    [(0, 4), (1, 5), (2, 6)],
    [(0, 5), (1, 6), (2, 7)],
    [(0, 6), (1, 4), (2, 5)],
    [(0, 11), (1, 11), (2, 10)],
    [(1, 12), (0, 12), (2, 4)],
]


def _world(others: list[list[Card]]) -> GameState:
    deal = make_deal([list(ME), *map(list, others)], MUESTRA)
    assert not any(deal.has_flor)
    state = TrucoGame().reset(deal=deal, mano=0)
    assert state.current_player == 0 and state.phase == Phase.PLAY
    return state


@pytest.fixture
def world_a() -> GameState:
    return _world(STRONG)


@pytest.fixture
def world_b() -> GameState:
    return _world(WEAK)


def _decide(agent_cls, state: GameState):
    agent = agent_cls(seed=5, n_rollouts=6)
    legal = TrucoGame().legal_actions(state)
    return agent.choose_action(state, legal, 0), list(agent._cache.values())


# ── (a) hidden information must not leak ───────────────────────────────────────


def test_worlds_look_identical_to_seat_0(world_a: GameState, world_b: GameState) -> None:
    game = TrucoGame()
    legal = game.legal_actions(world_a)
    assert legal == game.legal_actions(world_b)
    assert world_a.manos != world_b.manos  # ...yet the hidden hands really differ
    for action in legal:
        assert _fair_state_key(world_a, 0, action) == _fair_state_key(world_b, 0, action)


@pytest.mark.parametrize(
    "agent_cls",
    [
        DeterminizedVonNeumannAgent,
        pytest.param(
            OmniscientVonNeumannAgent,
            marks=pytest.mark.xfail(
                strict=True,
                reason="legacy agent rolls out from the true deal: perfect information (#50)",
            ),
        ),
    ],
)
def test_decision_does_not_depend_on_hidden_hands(
    agent_cls, world_a: GameState, world_b: GameState
) -> None:
    """Same view from seat 0, different hidden hands -> same action and same EVs."""
    assert _decide(agent_cls, world_a) == _decide(agent_cls, world_b)


def test_determinize_output_depends_only_on_the_view(
    world_a: GameState, world_b: GameState
) -> None:
    assert determinize(world_a, 0, random.Random(3)) == determinize(world_b, 0, random.Random(3))


# ── determinize() unit tests ────────────────────────────────────────────────────


def _check_world(orig: GameState, det: GameState, p: int) -> None:
    """``det`` is a valid world for seat ``p``: same view, a consistent hidden deal."""
    for f in dataclasses.fields(orig):
        if f.name in _HIDDEN_PER_SEAT:
            assert getattr(det, f.name)[p] == getattr(orig, f.name)[p], f.name
        elif f.name != "has_flor":
            assert getattr(det, f.name) == getattr(orig, f.name), f.name
    assert det.has_flor == orig.has_flor
    played = _played_by(orig)
    pm, nm = orig.muestra
    everything = [orig.muestra]
    for s in range(6):
        assert len(det.cards_in_hand[s]) == len(orig.cards_in_hand[s])
        if s == p:
            assert sorted(det.manos[s]) == sorted(played[s] + det.cards_in_hand[s])
        else:
            assert det.manos[s] == played[s] + det.cards_in_hand[s]
        everything += det.manos[s]
        if s != p and s in orig.seats:
            assert tiene_flor(det.manos[s], pm, nm) == orig.has_flor[s]
    assert len(set(everything)) == len(everything) == 19  # no card dealt twice


def test_determinize_keeps_the_view_and_deals_a_consistent_world(world_a: GameState) -> None:
    before = copy.deepcopy(world_a)
    det = determinize(world_a, 0, random.Random(1))
    assert world_a == before  # the input is never mutated
    _check_world(world_a, det, 0)
    assert det.manos != world_a.manos  # and it really did resample


def test_determinize_holds_across_phases_seats_and_mid_hand_states() -> None:
    game = TrucoGame(rules=Rules(ley_de_juego=True))
    seen: set[Phase] = set()
    for seed in range(300):
        rng = random.Random(seed)
        seats = None if seed % 2 else [seed % 6, (seed + 3) % 6]
        state = game.reset(
            seed=seed, seats=seats, mano=seats[0] if seats else seed % 6, scores=[seed % 30, 5]
        )
        while state.phase != Phase.DONE:
            seen.add(state.phase)
            p = state.current_player
            _check_world(state, determinize(state, p, rng), p)
            game.apply_action(state, rng.choice(game.legal_actions(state)))
    assert seen >= {Phase.LEY, Phase.FLOR, Phase.PLAY}


def test_rejection_sampling_cost_with_flor_holders() -> None:
    """Flor is public, so samples must reproduce it; this is what that costs in tries."""
    # Seats 1 and 2 hold flor derecha (then also seat 3 in the second world).
    flor1, flor2, flor3 = (
        [(0, 2), (0, 3), (0, 4)],
        [(1, 1), (1, 2), (1, 3)],
        [(2, 1), (2, 2), (2, 4)],
    )
    filler = [[(0, 5), (1, 4), (2, 5)], [(0, 6), (1, 5), (2, 6)]]
    two = TrucoGame().reset(
        deal=make_deal([list(ME), flor1, flor2, [(0, 7), (1, 10), (2, 7)], *filler[:2]], MUESTRA),
        mano=0,
    )
    three = TrucoGame().reset(
        deal=make_deal([list(ME), flor1, flor2, flor3, *filler], MUESTRA), mano=0
    )
    assert [s for s in range(6) if two.has_flor[s]] == [1, 2]
    assert [s for s in range(6) if three.has_flor[s]] == [1, 2, 3]

    rng = random.Random(0)
    tries_two = [draw_consistent_hands(two, 0, rng)[1] for _ in range(100)]
    tries_three = [draw_consistent_hands(three, 0, rng)[1] for _ in range(2)]
    assert max(tries_two) < _MAX_DEAL_TRIES // 10
    assert max(tries_three) < _MAX_DEAL_TRIES // 2
    for state in (two, three):
        hands, _ = draw_consistent_hands(state, 0, rng)
        for s in (1, 2, 3):
            assert tiene_flor(hands[s], *MUESTRA) == state.has_flor[s]


# ── rare joint-flor states: exactness and the enumeration fallback (exp 013 arm A crash) ──

# Five flor holders (seats 1-5) against seat 0's one non-flor hand: the joint event "all five
# unseen hands have flor" has probability ~3e-5 per rejection try, so the 200k-try cap can be hit.
FIVE_FLOR = [
    [(0, 2), (0, 3), (0, 4)],
    [(0, 5), (0, 6), (0, 7)],
    [(1, 1), (1, 2), (1, 3)],
    [(1, 4), (1, 5), (1, 6)],
    [(2, 1), (2, 2), (2, 4)],
]


def _five_flor_state() -> GameState:
    deal = make_deal([list(ME), *map(list, FIVE_FLOR)], MUESTRA)
    assert deal.has_flor == (False, True, True, True, True, True)
    return TrucoGame().reset(deal=deal, mano=0)


def _reference_rejection(state: GameState, player_idx: int, rng: random.Random):
    """Verbatim copy of the pre-fix joint-rejection loop (cap aside): the bit-identity oracle."""
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
    raise RuntimeError("cap")


def test_the_true_hidden_hands_always_satisfy_the_acceptance_predicate() -> None:
    """The true deal is consistent by construction, at every decision of random games."""
    game = TrucoGame(rules=Rules(ley_de_juego=True))
    checked = 0
    for seed in range(300):
        rng = random.Random(seed)
        seats = None if seed % 2 else [seed % 6, (seed + 3) % 6]
        state = game.reset(seed=seed, seats=seats, mano=seats[0] if seats else seed % 6)
        while state.phase != Phase.DONE:
            p = state.current_player
            truth = {s: list(state.cards_in_hand[s]) for s in range(6) if s != p}
            assert _is_consistent(state, truth, _played_by(state)), (seed, p)
            checked += 1
            game.apply_action(state, rng.choice(game.legal_actions(state)))
    assert checked > 1000
    state = _five_flor_state()
    truth = {s: list(state.cards_in_hand[s]) for s in range(1, 6)}
    assert _is_consistent(state, truth, _played_by(state))


def test_accepted_draws_are_bit_identical_to_the_old_rejection_loop() -> None:
    """The fallback only runs where the old code raised: same hands, tries and RNG consumption."""
    game = TrucoGame()
    states = [_five_flor_state()]
    for seed in range(40):
        rng = random.Random(seed)
        state = game.reset(seed=seed)
        for _ in range(seed % 6):
            legal = game.legal_actions(state)
            if state.phase == Phase.DONE or not legal:
                break
            game.apply_action(state, rng.choice(legal))
        if state.phase != Phase.DONE:
            states.append(state)
    for i, state in enumerate(states):
        p = state.current_player
        old_rng, new_rng = random.Random(i), random.Random(i)
        old = _reference_rejection(state, p, old_rng)
        assert draw_consistent_hands(state, p, new_rng) == old
        assert old_rng.getstate() == new_rng.getstate()


def test_enumeration_fallback_deals_a_valid_world_when_the_cap_is_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _five_flor_state()
    monkeypatch.setattr("agents.determinized_von_neumann_agent._MAX_DEAL_TRIES", 20)
    rng = random.Random(0)
    played = _played_by(state)
    for _ in range(30):
        hands, tries = draw_consistent_hands(state, 0, rng)
        assert tries > 20  # past the (patched) cap: this came from the fallback
        assert _is_consistent(state, hands, played)
        cards = [c for h in hands.values() for c in h]
        assert len(set(cards)) == 15 and MUESTRA not in cards and not set(cards) & set(ME)
    det = determinize(state, 0, rng)
    _check_world(state, det, 0)


def test_the_real_cap_never_raises_on_a_five_flor_state() -> None:
    """Many draws, real cap: none may raise (the exp 013 arm A failure mode)."""
    state = _five_flor_state()
    rng = random.Random(1)
    for _ in range(5):
        hands, _ = draw_consistent_hands(state, 0, rng)
        assert _is_consistent(state, hands, _played_by(state))


def test_enumeration_fallback_matches_the_rejection_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same target distribution: compare marginals of a flor-pinned and a free seat."""
    two = TrucoGame().reset(
        deal=make_deal(
            [
                list(ME),
                [(0, 2), (0, 3), (0, 4)],
                [(1, 1), (1, 2), (1, 3)],
                [(0, 7), (1, 10), (2, 7)],
                [(0, 5), (1, 4), (2, 5)],
                [(0, 6), (1, 5), (2, 6)],
            ],
            MUESTRA,
        ),
        mano=0,
    )
    n = 3000

    def stats(rng: random.Random) -> tuple[float, float]:
        seat1_suit0 = seat3_rich = 0
        for _ in range(n):
            hands, _ = draw_consistent_hands(two, 0, rng)
            seat1_suit0 += sum(c[0] == 0 for c in hands[1]) == 3
            seat3_rich += any(c[0] == 3 for c in hands[3])
        return seat1_suit0 / n, seat3_rich / n

    rejection = stats(random.Random(11))
    monkeypatch.setattr("agents.determinized_von_neumann_agent._MAX_DEAL_TRIES", 0)
    fallback = stats(random.Random(12))
    for a, b in zip(rejection, fallback, strict=True):
        assert abs(a - b) < 0.045, (rejection, fallback)  # ~5 sigma at n = 3000


# ── (b) determinism ──────────────────────────────────────────────────────────────


def test_same_seed_same_decisions_and_cache(world_a: GameState) -> None:
    assert _decide(DeterminizedVonNeumannAgent, world_a) == _decide(
        DeterminizedVonNeumannAgent, world_a
    )


def test_same_seed_plays_the_same_hand() -> None:
    def play() -> list[int]:
        game = TrucoGame()
        agents = [DeterminizedVonNeumannAgent(seed=7 + i, n_rollouts=2) for i in range(6)]
        state = game.reset(seed=11)
        trace: list[int] = []
        while state.phase != Phase.DONE:
            p = state.current_player
            action = agents[p].choose_action(state, game.legal_actions(state), p)
            trace.append(int(action))
            game.apply_action(state, action)
        return trace

    assert play() == play()


# ── cache isolation ────────────────────────────────────────────────────────────────


def test_fair_key_covers_the_public_state(world_a: GameState, world_b: GameState) -> None:
    action = TrucoGame().legal_actions(world_a)[0]
    base = _fair_state_key(world_a, 0, action)
    other_muestra = copy.deepcopy(world_a)
    other_muestra.muestra = (3, 6)
    other_points = copy.deepcopy(world_a)
    other_points.hand_pts = [1, 0]
    assert _fair_state_key(other_muestra, 0, action) != base
    assert _fair_state_key(other_points, 0, action) != base
    assert _fair_state_key(world_a, 1, action) != base  # a different seat's view
    assert _fair_state_key(world_b, 0, action) == base  # only hidden hands differ


def test_cache_round_trips_with_a_format_header(tmp_path: Path, world_a: GameState) -> None:
    path = tmp_path / "vn.json"
    agent = DeterminizedVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)
    agent.choose_action(world_a, TrucoGame().legal_actions(world_a), 0)
    agent.save_cache()
    assert json.loads(path.read_text())["format"] == CACHE_FORMAT
    reloaded = DeterminizedVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)
    assert reloaded._cache == agent._cache and reloaded._cache


def test_legacy_cache_files_are_refused(tmp_path: Path, world_a: GameState) -> None:
    path = tmp_path / "legacy.json"
    legacy = OmniscientVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)
    legacy.choose_action(world_a, TrucoGame().legal_actions(world_a), 0)
    legacy.save_cache()
    assert path.exists()
    with pytest.raises(ValueError, match="legacy"):
        DeterminizedVonNeumannAgent(seed=1, n_rollouts=2, cache_path=path)


# ── registries ────────────────────────────────────────────────────────────────────


def test_benchmark_registers_the_fair_variant_with_its_own_cache(tmp_path: Path) -> None:
    shared = tmp_path / "ev.json"
    fair = benchmark._build_agent(
        "von_neumann_determinized", 3, rollouts=2, cache_path=shared, rl_agent=None
    )
    legacy = benchmark._build_agent("von_neumann", 3, rollouts=2, cache_path=shared, rl_agent=None)
    assert isinstance(fair, DeterminizedVonNeumannAgent)
    assert type(legacy) is OmniscientVonNeumannAgent
    assert isinstance(legacy, OmniscientVonNeumannAgent)
    assert fair._cfg.cache_path == tmp_path / "ev.determinized.json" != legacy._cfg.cache_path
    assert "von_neumann_determinized_vs_threshold" in benchmark.MODES
    assert benchmark.MODES["von_neumann_vs_threshold"].lineup == ("von_neumann", "threshold")


def test_league_registers_the_fair_variant_beside_the_legacy_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(league_010, "VN_ROLLOUTS", 1)
    fair = league_010._triplet("vonneumann_determinized", (0, 2, 4), 7, {}, Path("."))
    assert [type(a) for a in fair] == [DeterminizedVonNeumannAgent] * 3
    for a in fair:
        assert isinstance(a, DeterminizedVonNeumannAgent)
        assert a._cfg.cache_path is None and a._cfg.n_rollouts == 1
    legacy = league_010._triplet("vonneumann", (0, 2, 4), 7, {}, Path("."))
    assert [type(a) for a in legacy] == [OmniscientVonNeumannAgent] * 3
