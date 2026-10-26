"""CLI: python -m components.gastro_source --config config.yaml [--menu-limit N]"""

import argparse
import sys

import yaml

from .core import run


def main():
    parser = argparse.ArgumentParser(description="C2: Fetch mountain restaurant data")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit-batches", type=int,
                        help="Limit total restaurants (for quick pipeline tests)")
    parser.add_argument("--menu-limit", type=int,
                        help="Limit menu extractions (Playwright+LLM) to N websites")
    parser.add_argument("--scrape-menus", action="store_true",
                        help="Enable menu scraping (overrides config.gastro.scrape_menus)")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    if args.scrape_menus:
        cfg.setdefault("gastro", {})["scrape_menus"] = True

    try:
        run(cfg, limit_batches=args.limit_batches, menu_limit=args.menu_limit)
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
