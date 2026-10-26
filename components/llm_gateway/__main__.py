"""CLI entry point for the LLM Gateway (not typically called directly)."""

import argparse
import sys
from pathlib import Path

from common.config import load


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Gateway – test connectivity")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    cfg = load(args.config)
    provider = cfg.get("llm", {}).get("provider", "auto")
    print(f"LLM Gateway ready. Provider setting: {provider}")
    print("This component is used as a library by C1 and C2.")


if __name__ == "__main__":
    main()
