"""Pipeline: run components in order."""

import argparse
import sys
import yaml
from pathlib import Path


STEPS = [
    ("C1: resort_source", "components.resort_source", True),
    ("C2: gastro_source", "components.gastro_source", False),
    ("C3: geo_matcher", "components.geo_matcher", False),
    ("C4: cost_model", "components.cost_model", True),
    ("C5: clustering", "components.clustering", True),
    ("C6: dashboard", "components.dashboard", True),
    ("C7: validator (sample)", "components.validator", True),
]


def run_pipeline(config_path: str = "config.yaml", mock: bool = False, yes: bool = False):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    if mock:
        cfg["llm"]["provider"] = "mock"
        cfg["resorts"]["min_items"] = 3

    include_lunch = cfg.get("include_lunch_cost", False)

    for step_name, module_name, always_run in STEPS:
        if not always_run and not include_lunch:
            print(f"  SKIP {step_name} (include_lunch_cost: false)")
            continue

        print(f"  RUN  {step_name}")

        try:
            mod = __import__(module_name, fromlist=["core"])
            core = mod.core

            if module_name == "components.validator":
                core.run(cfg, mode="sample")
            elif module_name in ("components.resort_source", "components.gastro_source"):
                if mock:
                    core.run(cfg, limit_batches=1)
                else:
                    core.run(cfg)
            else:
                core.run(cfg)

            print(f"  OK   {step_name}")
        except SystemExit as e:
            if e.code != 0:
                print(f"  FAIL {step_name} (exit {e.code})")
                sys.exit(e.code)
        except Exception as e:
            print(f"  FAIL {step_name}: {e}")
            sys.exit(1)

    print("\nPipeline complete.")


def main():
    parser = argparse.ArgumentParser(description="Run the full pipeline")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM provider")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()
    run_pipeline(args.config, mock=args.mock, yes=args.yes)


if __name__ == "__main__":
    main()
