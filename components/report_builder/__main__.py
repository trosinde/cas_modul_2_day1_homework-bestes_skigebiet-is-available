import argparse
import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C8: Report Builder")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    run(cfg)


if __name__ == "__main__":
    main()
