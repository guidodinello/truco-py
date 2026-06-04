# truco-py — Agent Code Guidelines

These guidelines encode the conventions established during the project's refactoring.
Follow them for all new code; apply them when touching existing code.

---

## Running the project

```bash
uv pip install -e .          # editable install — do this once on a fresh clone
uv run ruff check .          # lint (must be clean before committing)
uv run ruff check --fix .    # auto-fix what ruff can
uv run pytest tests/ -v      # run test suite (must be green before committing)
pre-commit install           # install git hooks (once per clone)
```

**Never invoke `python3` directly.** Always use `uv run python` (or `uv run <script>`) so
the uv-managed virtual environment and pinned dependencies are used.

```bash
# Good
uv run python scripts/benchmark.py
uv run python -c "import engine; print(engine.__file__)"

# Bad — bypasses the venv
python3 scripts/benchmark.py
```

---

## Running commands

**Never invoke `python3` directly.** Always use `uv run python` (or `uv run <script>`) so
the uv-managed virtual environment and pinned dependencies are used.

```bash
# Good
uv run python scripts/benchmark.py
uv run python -c "import engine; print(engine.__file__)"

# Bad — bypasses the venv
python3 scripts/benchmark.py
```

---

## Imports

**Never use `sys.path.insert` or `sys.path.append`.**
The project is installed as an editable package (`uv pip install -e .`), so all
top-level packages (`engine`, `agents`, `training`, `experimentos`, `scripts`) are
importable without path manipulation.

```python
# Good
from engine.game import TrucoGame
from engine.truco import construir_mazo
from agents.threshold_agent import ThresholdAgent

# Bad
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from truco import construir_mazo
```

Use **relative imports** inside a package and **absolute imports** across packages.

---

## Logging

**Never use `print()` for status, progress, or diagnostic output.**
Use the two-handler logger from `log.py` instead.

```python
from log import get_logger

# stdout only
logger = get_logger(__name__)

# stdout + file (preferred for long-running scripts)
logger = get_logger("train", LOG_DIR / "train.log")

logger.info("Training started: %d steps", total_steps)
logger.warning("Win rate unexpectedly low: %.2f", rate)
logger.error("Unknown mode: %s", mode)
```

Use `%`-style formatting, not f-strings, in logger calls (defers string formatting
until the message is actually emitted).

`print()` is acceptable only for structured report output that is the *primary product*
of a script (e.g. the benchmark table in `scripts/benchmark.py`).

---

## Dataclasses and immutability

Use `@dataclass(slots=True)` for all new dataclasses — it catches typos and saves
memory.

Use `@dataclass(frozen=True, slots=True)` for data that is set once and never mutated.

```python
from dataclasses import dataclass

# Immutable deal snapshot — set once at deal time
@dataclass(frozen=True, slots=True)
class Deal:
    manos: tuple[tuple[tuple[int, int], ...], ...]
    muestra: tuple[int, int]

# Mutable game state — mutated throughout the hand
@dataclass(slots=True)
class GameState:
    phase: Phase
    scores: list[int]
```

Prefer `tuple` over `list` for fields that are never mutated after construction.
Always write full container type hints — never bare `list` or `dict`.

```python
# Good
cards: list[tuple[int, int]]
tricks: list[dict[int, tuple[int, int]]]

# Bad
cards: list
tricks: list
```

---

## Protocols instead of ABCs

Use `typing.Protocol` with `@runtime_checkable` to define structural interfaces.
Concrete classes do **not** inherit from the Protocol — they satisfy it structurally.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Agent(Protocol):
    def choose_action(self, state: GameState, legal_actions: list[Action], player_idx: int) -> Action: ...
    def reset(self) -> None: ...
```

```python
# Concrete class — no inheritance needed
class RandomAgent:
    def choose_action(self, state, legal_actions, player_idx):
        return random.choice(legal_actions)

    def reset(self) -> None:
        pass

# isinstance still works at runtime
assert isinstance(RandomAgent(), Agent)  # True
```

Use ABCs only when concrete classes share implementation (not just an interface).

---

## Named constants

Never use raw magic numbers for game rules. Define named constants at the module
level near the code that uses them.

```python
# Good — in engine/game.py
FLOR_CHICO_PTS = 3    # flor chico (first bid) is worth 3 pts
REAL_ENVIDO_PTS = 3   # real envido adds 3 pts to the stake
RETRUCO_PTS = 3       # retruco stake value

state.flor_stake = FLOR_CHICO_PTS

# Bad
state.flor_stake = 3
```

For action-space sizes, always reference `N_ACTIONS` from `engine.actions` — never
hardcode `53`.

---

## Configuration

When a function takes more than ~4 settings parameters, bundle them into a typed
dataclass config object instead of passing them individually.

```python
# Good — config is inspectable, loggable, and easy to extend
from dataclasses import dataclass

@dataclass(slots=True)
class TrainConfig:
    opponent_mode: str
    total_steps: int
    n_envs: int
    shaped_reward: bool
    seed: int
    checkpoint_freq: int
    load_checkpoint: str | None = None

def train(cfg: TrainConfig) -> None:
    logger.info("opponent=%s steps=%d envs=%d", cfg.opponent_mode, cfg.total_steps, cfg.n_envs)
    ...

# Bad — long argument lists are hard to pass around and log
def train(opponent_mode, total_steps, n_envs, shaped_reward, seed, checkpoint_freq, load_checkpoint):
    ...
```

Argparse stays at the CLI boundary and populates the config object:

```python
def main():
    args = parser.parse_args()
    cfg = TrainConfig(opponent_mode=args.opponents, total_steps=args.steps, ...)
    train(cfg)
```

**Pydantic is not yet a dependency.** Reach for `pydantic-settings` only if you need
config from multiple sources (env vars, YAML files, CLI flags) with merge priority and
validation error messages. For the current research scripts, a plain dataclass suffices.

---

## Path handling

**Always use `pathlib.Path` — never bare strings for file paths.**

```python
from pathlib import Path

# Good
ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = ROOT / "checkpoints"
LOG_DIR = ROOT / "logs"
model.save(str(CHECKPOINT_DIR / f"truco_{step}.zip"))  # str() only at the boundary

# Bad
checkpoint_dir = "/home/user/project/checkpoints"
path = checkpoint_dir + "/" + f"truco_{step}.zip"
```

Use `/` for joining, `.parent` for navigation, and `.stem` / `.suffix` / `.name` for
introspection. Convert to `str` only when a third-party API requires it (e.g.
`model.save(str(path))`).

---

## Type annotations

Annotate all public functions with parameter types and return types.

```python
# Good
def card_strength(palo: int, numero: int, palo_muestra: int, numero_muestra: int) -> int: ...
def obs_to_vector(state: GameState, player_idx: int) -> np.ndarray: ...

# Bad
def card_strength(palo, numero, palo_muestra, numero_muestra): ...
```

Use modern Python 3.10+ union syntax (`X | Y`, `list[T]`, `tuple[A, B]`) — never
`Optional[X]`, `List[T]`, or `Union[A, B]`.

---

## Tests

All new engine logic, encoders, and agents must have tests in `tests/`.

- `tests/test_engine.py` — game loop invariants (`reset`, `legal_actions`, `apply_action`, full game)
- `tests/test_state_encoder.py` — observation shape, dtype, bounds, feature correctness
- `tests/test_agents.py` — Protocol conformance, legal action compliance, `reset()` safety

Tests must pass before merging:

```bash
uv run pytest tests/ -v
```

---

## Prefer the standard library

**Before writing a utility function, check if the stdlib already has it.**
Python's standard library covers a surprising amount of ground. Custom implementations
are harder to read, harder to test, and don't benefit from years of CPython optimisation.
The rule: stdlib first, third-party second, in-house last.

The modules most relevant to this codebase:

### functools — caching and higher-order functions

Never write manual dicts for memoisation when `@cache` or `@lru_cache` works:

```python
# Bad — manual cache
_strength_cache: dict[tuple, int] = {}
def card_strength(palo, numero, palo_muestra, numero_muestra):
    key = (palo, numero, palo_muestra, numero_muestra)
    if key not in _strength_cache:
        _strength_cache[key] = _compute(...)
    return _strength_cache[key]

# Good
from functools import cache

@cache
def card_strength(palo: int, numero: int, palo_muestra: int, numero_muestra: int) -> int:
    return _compute(...)
```

Other useful tools from `functools`:
- `partial` — fix some arguments of a function, useful for env factory callbacks
- `wraps` — preserve metadata when writing decorators
- `reduce` — fold a sequence into a single value

### itertools — iteration without manual loops

Reach for `itertools` before writing a loop that combines, filters, or sequences iterables:

```python
from itertools import chain, combinations, takewhile

# Flatten a list of lists
all_cards = list(chain.from_iterable(state.manos))

# All 2-card combinations from a hand
pairs = list(combinations(hand, 2))

# Take cards while they meet a condition
strong = list(takewhile(lambda c: strength(c) > 5, sorted_hand))
```

### contextlib — context managers

Use `@contextmanager` instead of writing a class with `__enter__`/`__exit__` for simple
resource patterns:

```python
from contextlib import contextmanager
import time

@contextmanager
def timed(label: str):
    t0 = time.perf_counter()
    yield
    logger.info("%s took %.3fs", label, time.perf_counter() - t0)

with timed("game simulation"):
    results = simulate(n=100_000)
```

Other useful tools: `suppress` (silence specific exceptions cleanly),
`redirect_stdout` (capture script output in tests).

### timeit — micro-benchmarks

Use `timeit` for measuring small code snippets, not manual `perf_counter` loops:

```python
import timeit

# How fast is card_strength?
t = timeit.timeit(
    "card_strength(0, 1, 2, 7)",
    setup="from engine.card import card_strength",
    number=100_000,
)
print(f"{t / 100_000 * 1e6:.2f} µs per call")
```

For whole-script profiling use `uv run python -m cProfile -s cumtime script.py`.

---

## Linting

ruff is the single linter and formatter. The active rule sets are `E, F, I, UP, B, SIM`
(see `pyproject.toml`). Run before every commit:

```bash
uv run ruff check --fix .
```

Inline `# noqa` suppression is a last resort. Prefer fixing the root cause.
If suppression is truly needed, use `per-file-ignores` in `pyproject.toml` with a comment
explaining why.

---

## Package structure

| Package | Contents |
|---------|----------|
| `engine/` | Game rules, state, card logic, Monte Carlo sim (`engine/truco.py`) |
| `agents/` | Agent implementations + `Agent` Protocol in `agents/base.py` |
| `training/` | Gym env, reward functions, self-play, state encoder, train entry point |
| `experimentos/` | Monte Carlo experiment scripts |
| `scripts/` | CLI tools: benchmark, BC pre-trainer |
| `tests/` | pytest test suite |
| `log.py` | Two-handler logger factory (root-level, importable from anywhere) |
| `truco.py` | Compatibility shim only — logic lives in `engine/truco.py` |
