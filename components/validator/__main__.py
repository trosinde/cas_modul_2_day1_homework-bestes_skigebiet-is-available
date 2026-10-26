"""CLI: python -m components.validator --config config.yaml --mode sample|validate"""

import argparse
import sys

import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C7: Validator")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--mode", choices=["sample", "validate"], default="sample",
    )
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    run(cfg, mode=args.mode)


if __name__ == "__main__":
    main()
