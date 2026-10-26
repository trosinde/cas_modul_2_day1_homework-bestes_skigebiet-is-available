"""CLI: python -m components.clustering --config config.yaml"""

import argparse
import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C5: Clustering")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    run(cfg)


if __name__ == "__main__":
    main()
