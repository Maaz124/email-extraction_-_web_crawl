"""
pipeline/log.py
Shared file logger for the pipeline package.
Writes to logs/pipeline.log alongside the UI logger.
"""

import logging
from pathlib import Path

_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("pipeline")
if not logger.handlers:
    _fh = logging.FileHandler(_LOGS_DIR / "pipeline.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(_fh)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
