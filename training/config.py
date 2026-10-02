"""
TrainConfig: every setting of one experiment-009 training run, in one inspectable,
loggable object (argparse stays at the CLI boundary in ``training/run.py``).

Run layout (all under ``runs_root``, which is a symlink to the HDD):

    <runs_root>/<run_id>/            ckpt/ eval/ tb/ train.log run.json STOP
    <runs_root>/pool/<run_id>/       snap_<step>.zip   (the run-scoped OpponentPool)
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS_ROOT = ROOT / "runs" / "009"

# Roles an opponent team can be drawn from; the integer is what the env reports in ``info``.
ROLE_THRESHOLD, ROLE_RANDOM, ROLE_SELF = 0, 1, 2
ROLE_NAMES = ("threshold", "random", "self")

SNAPSHOT_GLOB = "snap_*.zip"
STEP_DIGITS = 10  # zero-padded so lexical sort == step order

PartnerPolicy = Literal["snapshot", "threshold", "pool"]
RewardKind = Literal["sign", "diff"]
VecEnvKind = Literal["subproc", "dummy"]
# Where snapshot opponents/partners run inference: a batching server thread on the CPU or GPU,
# or "local" = each env worker holds its own single-threaded CPU copy (no server).
InferenceKind = Literal["cpu", "cuda", "local"]


@dataclass(frozen=True, slots=True)
class OpponentMix:
    """Probabilities of the opponent *team* being Threshold / Random / an own snapshot."""

    threshold: float = 0.4
    random: float = 0.2
    selfplay: float = 0.4

    def __post_init__(self) -> None:
        weights = (self.threshold, self.random, self.selfplay)
        if any(w < 0 for w in weights) or abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError(f"opponent mix must be non-negative and sum to 1, got {weights}")

    @property
    def weights(self) -> tuple[float, float, float]:
        return (self.threshold, self.random, self.selfplay)

    @classmethod
    def parse(cls, text: str) -> "OpponentMix":
        """``"thr=0.4,rand=0.2,self=0.4"`` -> OpponentMix (all three keys required)."""
        keys = {"thr": "threshold", "rand": "random", "self": "selfplay"}
        parts = dict(item.split("=") for item in text.split(","))
        if set(parts) != set(keys):
            raise ValueError(f"--opponent-mix needs exactly thr=,rand=,self= (got {sorted(parts)})")
        return cls(**{keys[k]: float(v) for k, v in parts.items()})

    def __str__(self) -> str:
        return f"thr={self.threshold},rand={self.random},self={self.selfplay}"


def snapshot_name(step: int) -> str:
    return f"snap_{step:0{STEP_DIGITS}d}.zip"


@dataclass(slots=True)
class TrainConfig:
    run_id: str
    init_checkpoint: Path | None = None  # BC init (fresh runs only)
    total_steps: int = 20_000_000
    n_envs: int = 16
    seed: int = 42
    learning_rate: float = 1e-4  # D7
    ent_coef: float = 0.01  # D8
    opponent_mix: OpponentMix = field(default_factory=OpponentMix)  # D1
    partners: PartnerPolicy = "snapshot"  # D2
    reward: RewardKind = "diff"  # D5
    reward_scale: float = 15.0
    context_bank: Path | None = None  # D4
    checkpoint_every: int = 250_000
    snapshot_every: int = 1_000_000
    eval_every: int = 250_000
    eval_n: int = 200
    device: str = "auto"
    vec_env: VecEnvKind = "subproc"
    inference: InferenceKind = "cpu"
    runs_root: Path = DEFAULT_RUNS_ROOT

    def __post_init__(self) -> None:
        for name in ("snapshot_every", "eval_every"):
            if getattr(self, name) % self.checkpoint_every:
                raise ValueError(f"{name} must be a multiple of checkpoint_every")
        if self.eval_n % 2:
            raise ValueError("eval_n must be even (2-role seat rotation)")

    @property
    def use_inference_server(self) -> bool:
        return self.inference != "local"

    # ── layout ────────────────────────────────────────────────────────────
    @property
    def run_dir(self) -> Path:
        return self.runs_root / self.run_id

    @property
    def ckpt_dir(self) -> Path:
        return self.run_dir / "ckpt"

    @property
    def eval_dir(self) -> Path:
        return self.run_dir / "eval"

    @property
    def tb_dir(self) -> Path:
        return self.run_dir / "tb"

    @property
    def log_path(self) -> Path:
        return self.run_dir / "train.log"

    @property
    def run_json(self) -> Path:
        return self.run_dir / "run.json"

    @property
    def stop_file(self) -> Path:
        return self.run_dir / "STOP"

    @property
    def pool_root(self) -> Path:
        """``OpponentPool(directory=pool_root, run_id=run_id)`` globs ``pool_root/run_id``."""
        return self.runs_root / "pool"

    @property
    def pool_dir(self) -> Path:
        return self.pool_root / self.run_id

    # ── (de)serialisation for run.json ────────────────────────────────────
    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["opponent_mix"] = str(self.opponent_mix)
        for k in ("init_checkpoint", "context_bank", "runs_root"):
            d[k] = None if d[k] is None else str(d[k])
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "TrainConfig":
        d = dict(d)
        d["opponent_mix"] = OpponentMix.parse(d["opponent_mix"])
        for k in ("init_checkpoint", "context_bank"):
            d[k] = None if d[k] is None else Path(d[k])
        d["runs_root"] = Path(d["runs_root"])
        return cls(**d)


# Fields that must not change across a --resume: they define the experiment.
IMMUTABLE_ON_RESUME = (
    "seed",
    "learning_rate",
    "ent_coef",
    "opponent_mix",
    "partners",
    "reward",
    "reward_scale",
    "context_bank",
)
