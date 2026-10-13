"""Entry point: ``uv run python -m finm37000_grp2``."""

import argparse
import logging

from . import config
from .pipeline import run_data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m finm37000_grp2",
        description="Download ES mbp-1 data, clean it and write Parquet.",
    )
    parser.add_argument(
        "--sample",
        choices=sorted(config.SAMPLES),
        default="dev",
        help="sample period from config.SAMPLES (default: dev)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="download and clean again even if output already exists",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use synthetic data instead of Databento (no API key needed)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    paths = run_data(args.sample, force=args.force, offline=args.offline)
    print(f"{len(paths)} clean session file(s) in {paths[0].parent if paths else '-'}")


if __name__ == "__main__":
    main()
