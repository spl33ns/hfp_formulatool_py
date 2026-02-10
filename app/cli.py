from __future__ import annotations

import argparse
import logging
from pathlib import Path

from core.logging_conf import setup_run_logging
from core.pipeline import process_excel
from core.stages import Stage
from core.utils import create_run_output_dir

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Headless runner for the Truth Table Generator pipeline.")
    parser.add_argument("--input", required=True, type=Path, help="Path to input Excel (.xlsx).")
    parser.add_argument("--output", default=Path("output"), type=Path, help="Output root folder.")
    parser.add_argument(
        "--mapping-file",
        default=None,
        type=Path,
        help="Optional mapping file (.csv with TAB delimiter, UTF-8; columns 1/3/8).",
    )
    parser.add_argument("--max-rules", default=2000, type=int, help="Max DNF rules per section.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    args = parser.parse_args(argv)

    level = getattr(logging, args.log_level)
    run_output_dir = create_run_output_dir(str(args.output))
    log_path = setup_run_logging(output_root=run_output_dir, level=level, gui_emit_line=None)
    print(f"Output directory: {run_output_dir}")
    print(f"Log file: {log_path}")

    logger.info("CLI start", extra={"stage": Stage.RUN.value, "section": "-"})
    logger.info("Log file: %s", log_path, extra={"stage": Stage.RUN.value, "section": "-"})

    try:
        results = process_excel(args.input, run_output_dir, args.max_rules, mapping_path=args.mapping_file)
    except Exception:
        logger.exception("Pipeline failed", extra={"stage": Stage.RUN.value, "section": "-"})
        return 2

    total = sum(len(sections) for sections in results.values()) if results else 0
    succeeded = sum(len([s for s in sections if s.status == "OK"]) for sections in results.values()) if results else 0
    failed = total - succeeded
    logger.info("Summary: total=%s succeeded=%s failed=%s", total, succeeded, failed, extra={"stage": Stage.RUN.value, "section": "-"})
    print(f"Summary: total={total} succeeded={succeeded} failed={failed}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
