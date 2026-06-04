# Improvements Backlog

Concrete improvements that are worth doing but not urgent enough to block current work.
Grouped by subsystem.

---

## Logging

### Log rotation and timestamped filenames

**Current state**: `log.py` uses a plain `FileHandler` that appends to the same file
indefinitely (e.g. `logs/train.log`). Multiple training runs accumulate in a single file
with no way to tell them apart.

**Improvement**: switch to timestamped filenames + automatic cleanup of old files.

```python
from datetime import datetime
from logging.handlers import RotatingFileHandler

def get_logger(name: str, log_file: Path | None = None, max_bytes: int = 5_000_000, backup_count: int = 5) -> logging.Logger:
    ...
    if log_file is not None:
        # e.g. logs/train_2026-04-12T14-30.log
        stamped = log_file.with_stem(f"{log_file.stem}_{datetime.now().strftime('%Y-%m-%dT%H-%M')}")
        fh = RotatingFileHandler(stamped, maxBytes=max_bytes, backupCount=backup_count)
        ...
```

Alternatively, add a standalone `prune_old_logs(log_dir, keep_days=14)` helper that
deletes `.log` files older than a threshold — useful to call at the start of a long
training run.

**Why not now**: log files are small and few; the problem will matter once continuous
training runs become routine.

---

## Training

### Pause/resume — current state

**Already in place**: `train.py` saves a checkpoint every `checkpoint_freq` steps and
exposes `--load <path>` to resume from any `.zip`. The checkpoint directory currently
holds 11 threshold-phase snapshots at 500k-step intervals, plus finals for each mode.

**What's missing**:
- No automatic detection of the latest checkpoint for a given mode — the user must
  supply the path manually.
- No metadata file alongside each checkpoint (step count, training config, wall time)
  so it's easy to see what a `.zip` actually represents without parsing the filename.
- `SelfPlayManager` rebuilds the pool from scratch on resume rather than persisting
  the pool state.

**Improvement ideas**:
1. Add a `checkpoints/manifest.json` that maps checkpoint path → `{step, mode, seed, timestamp}`.
   `CheckpointCallback` writes to it on every save; `--load latest` resolves automatically.
2. Save a `TrainConfig` dataclass alongside each checkpoint (as JSON) so any run is
   fully reproducible from its checkpoint directory alone.
3. Persist the `SelfPlayManager` pool to disk so self-play resumes with the same
   opponent pool instead of re-starting from `ThresholdAgent` fallback.

### Training config dataclass

`train()` currently takes 7 individual parameters. As hyperparameter search grows,
this will get unwieldy. Bundle into a `TrainConfig` dataclass (as described in
`CLAUDE.md`) and log the full config at the start of every run — makes TensorBoard
runs reproducible from logs alone.

---

## Configuration

### Pydantic settings (future, not now)

Once config needs to come from more than one source (CLI flags + environment variables
for cluster submission + a YAML sweep file), replace the `TrainConfig` dataclass with
`pydantic-settings`. It handles merge priority and gives typed validation errors at
startup rather than at the first use of a bad value.

**Trigger**: when running hyperparameter sweeps on a cluster where env vars override
defaults, or when a YAML config file is more convenient than a long CLI invocation.
Until then, the plain dataclass is simpler and sufficient.

---

## Checkpoints

### Checkpoint pruning

The `checkpoints/` directory currently holds every snapshot ever saved (11+ `.zip`
files from the threshold phase alone, ~tens of MB each). For long self-play runs this
will grow large.

**Improvement**: add a `keep_last_n` parameter to `CheckpointCallback` that deletes
older checkpoints for the same training run after saving a new one, keeping only the N
most recent (default 5) plus the `_final.zip`.

```python
class CheckpointCallback:
    def __init__(self, ..., keep_last_n: int = 5):
        ...

    def _prune(self):
        pattern = CHECKPOINT_DIR.glob(f"{self.label}_*.zip")
        candidates = sorted(pattern, key=lambda p: p.stat().st_mtime)[:-self.keep_last_n]
        for old in candidates:
            old.unlink()
```
