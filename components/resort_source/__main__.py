"""CLI: python -m components.resort_source --config config.yaml [--run N] [--limit-batches N]"""

import argparse
import sys

import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C1: Fetch ski resort data")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--run", type=int, help="Run only this run number (1-3)")
    parser.add_argument("--limit-batches", type=int, help="Limit number of batches")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    try:
        run(cfg, limit_batches=args.limit_batches, single_run=args.run)
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
