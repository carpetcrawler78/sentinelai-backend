"""
SentinelAI (vigilex) -- PRR/ROR Signal Detection Worker.

Periodically calls run_prr_ror() for a time window and writes results
to processed.signal_results. The DB connection is managed inside
run_prr_ror() -- this worker does not open one directly.

Usage (from vigilex repo root, with SSH tunnel to Hetzner open):
    python -m vigilex.workers.signal               # continuous polling loop
    python -m vigilex.workers.signal --once        # single run, then exit
    python -m vigilex.workers.signal --dry-run     # compute but do not write to DB
    python -m vigilex.workers.signal --start 2024-01-01 --end 2024-12-31
    python -m vigilex.workers.signal --once --dry-run  # smoke test (no DB write)

Required SSH tunnel for local development:
    ssh -L 5432:localhost:5432 cap@46.225.109.99
"""

import argparse
import logging
import sys
import time
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from vigilex.signals.prr_ror import run_prr_ror, DEFAULT_THRESHOLDS


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("vigilex.workers.signal")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_POLL_SECS = 3600  # 1 hour between runs in continuous mode


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_signal_loop(
    start_date: date,
    end_date: date,
    dry_run: bool,
    once: bool,
    poll_secs: int,
) -> None:
    """
    Repeatedly call run_prr_ror() for the given time window and log results.

    In continuous mode (once=False) the loop sleeps poll_secs seconds between
    runs. A single failed run is logged but does not abort the loop -- the
    worker will retry on the next wake-up.

    Args:
        start_date: analysis window start (inclusive)
        end_date:   analysis window end (inclusive)
        dry_run:    if True, compute but do not write to processed.signal_results
        once:       if True, exit after a single run
        poll_secs:  seconds to sleep between runs in continuous mode
    """
    while True:
        logger.info(
            "Signal run starting | window=%s to %s | dry_run=%s",
            start_date, end_date, dry_run,
        )
        try:
            results = run_prr_ror(
                start_date=start_date,
                end_date=end_date,
                dry_run=dry_run,
            )
            n_signals = sum(1 for r in results if r["is_signal"])
            logger.info(
                "Signal run complete: %d combinations evaluated, %d signals detected",
                len(results), n_signals,
            )
        except Exception as exc:
            # Log the full traceback so the root cause is visible in logs.
            # Do not re-raise -- a transient DB error should not kill the worker.
            logger.error("Signal run failed: %s", exc, exc_info=True)

        if once:
            logger.info("--once mode: exiting after single run.")
            break

        logger.info("Sleeping %ds before next run...", poll_secs)
        time.sleep(poll_secs)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SentinelAI PRR/ROR Signal Detection Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Continuous mode -- re-runs every hour (default)
  python -m vigilex.workers.signal

  # Single run over 2024 data, then exit
  python -m vigilex.workers.signal --once --start 2024-01-01 --end 2024-12-31

  # Smoke test -- compute but do not touch the DB
  python -m vigilex.workers.signal --once --dry-run
        """,
    )
    parser.add_argument(
        "--start", default="2024-01-01",
        help="Analysis window start date (YYYY-MM-DD, default: 2024-01-01)",
    )
    parser.add_argument(
        "--end", default=str(date.today()),
        help="Analysis window end date (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run once and exit (no polling loop)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute PRR/ROR but do not write results to processed.signal_results",
    )
    parser.add_argument(
        "--poll-secs", type=int, default=DEFAULT_POLL_SECS,
        help=f"Seconds between runs in continuous mode (default: {DEFAULT_POLL_SECS})",
    )
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    end_date   = date.fromisoformat(args.end)

    logger.info("=== SentinelAI Signal Worker starting ===")
    logger.info(
        "Config: window=%s to %s | once=%s | dry_run=%s | poll_secs=%d | thresholds=%s",
        start_date, end_date, args.once, args.dry_run, args.poll_secs, DEFAULT_THRESHOLDS,
    )

    run_signal_loop(
        start_date=start_date,
        end_date=end_date,
        dry_run=args.dry_run,
        once=args.once,
        poll_secs=args.poll_secs,
    )

    logger.info("=== Signal Worker finished ===")


if __name__ == "__main__":
    main()
