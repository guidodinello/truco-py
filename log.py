"""
Logging setup for truco-py.

Usage:
    from log import get_logger
    logger = get_logger(__name__)                      # stdout only
    logger = get_logger(__name__, Path("logs/x.log")) # stdout + file
"""

import logging
import sys
from pathlib import Path

_FMT = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")


def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    """
    Return a logger with a stdout StreamHandler and, optionally, a FileHandler.

    Idempotent: calling with the same name twice returns the already-configured
    logger without adding duplicate handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(_FMT)
    logger.addHandler(sh)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(_FMT)
        logger.addHandler(fh)

    logger.setLevel(logging.INFO)
    return logger
