"""Centralized debug log.

Writes a rotating debug log to <package>/logs/app.log. (The Qt UI hook from the
original tool was dropped along with the GUI.)
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    root = logging.getLogger("wordart")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    file_h = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    root.addHandler(file_h)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    root.addHandler(console)
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"wordart.{name}")
