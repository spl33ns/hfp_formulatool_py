from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable


LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(stage)s | %(section)s | %(name)s | %(message)s"


class DefaultFieldsFilter(logging.Filter):
    """Ensure formatter fields exist even if a logger forgets to set them via `extra=`."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - trivial
        if not hasattr(record, "stage"):
            record.stage = "-"
        if not hasattr(record, "section"):
            record.section = "-"
        return True


class GuiLogHandler(logging.Handler):
    """Handler that forwards formatted log lines to a UI callback (thread-safe if callback is)."""

    def __init__(self, emit_line: Callable[[str], None], level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._emit_line = emit_line

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - UI integration
        try:
            msg = self.format(record)
            self._emit_line(msg)
        except Exception:
            self.handleError(record)


def _make_run_log_path(output_root: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output_root / f"run_{ts}.log"
    if not base.exists():
        return base
    # Very fast reruns can collide within the same second.
    suffix = 1
    while True:
        candidate = output_root / f"run_{ts}_{suffix}.log"
        if not candidate.exists():
            return candidate
        suffix += 1


def _remove_previous_run_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        if getattr(handler, "_hfp_run_handler", False):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def setup_run_logging(
    *,
    output_root: Path,
    level: int = logging.INFO,
    gui_emit_line: Callable[[str], None] | None = None,
) -> Path:
    """Configure standard logging for one run.

    - File log: `output_root/run_YYYYmmdd_HHMMSS.log`
    - Optional GUI log handler via `gui_emit_line`
    """
    output_root.mkdir(parents=True, exist_ok=True)
    log_path = _make_run_log_path(output_root)

    root = logging.getLogger()
    root.setLevel(level)
    _remove_previous_run_handlers(root)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    defaults_filter = DefaultFieldsFilter()

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(defaults_filter)
    file_handler._hfp_run_handler = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    if gui_emit_line is not None:
        gui_handler = GuiLogHandler(gui_emit_line, level=level)
        gui_handler.setFormatter(formatter)
        gui_handler.addFilter(defaults_filter)
        gui_handler._hfp_run_handler = True  # type: ignore[attr-defined]
        root.addHandler(gui_handler)

    return log_path

