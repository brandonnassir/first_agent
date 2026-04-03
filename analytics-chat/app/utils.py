"""Shared utility helpers."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from uuid import uuid4


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        stream=sys.stdout,
    )


def generate_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = uuid4().hex[:8]
    return f"run_{ts}_{short}"
