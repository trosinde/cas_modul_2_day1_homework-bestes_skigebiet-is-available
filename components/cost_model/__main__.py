"""CLI: python -m components.cost_model --config config.yaml"""

import argparse
import sys

import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C4: Cost model")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    run(cfg)


if __name__ == "__main__":
    main()
