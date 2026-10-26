"""CLI: python -m components.geo_matcher --config config.yaml"""

import argparse
import sys

import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C3: Geo-match restaurants to resorts")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    try:
        run(cfg)
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
