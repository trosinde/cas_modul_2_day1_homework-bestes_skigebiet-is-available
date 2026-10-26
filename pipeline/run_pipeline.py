"""Pipeline: run components in order."""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml


STEPS = [
    ("C1: resort_source", "components.resort_source", True),
    ("C2: gastro_source", "components.gastro_source", False),
    ("C3: geo_matcher", "components.geo_matcher", False),
    ("C4: cost_model", "components.cost_model", True),
    ("C5: clustering", "components.clustering", True),
    ("C6: dashboard", "components.dashboard", True),
    ("C7: validator (sample)", "components.validator", True),
]


def _ts():
    return datetime.now().strftime("[%H:%M:%S]")


def run_pipeline(config_path: str = "config.yaml", mock: bool = False, yes: bool = False):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    if mock:
        cfg["llm"]["provider"] = "mock"
        cfg["resorts"]["min_items"] = 3

    include_lunch = cfg.get("include_lunch_cost", False)

    from common.paths import processed_dir
    proc = Path(processed_dir(cfg))
    gastro_data_exists = (proc / "resort_lunch.csv").exists()

    t_pipeline = time.monotonic()

    for step_name, module_name, always_run in STEPS:
        if not always_run and not include_lunch and not gastro_data_exists:
            print(f"{_ts()}  SKIP {step_name} (include_lunch_cost: false, no prior gastro data)", flush=True)
            continue

        print(f"{_ts()}  RUN  {step_name}", flush=True)
        t_step = time.monotonic()

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

            elapsed = time.monotonic() - t_step
            print(f"{_ts()}  OK   {step_name} ({elapsed:.1f}s)", flush=True)
        except SystemExit as e:
            if e.code != 0:
                elapsed = time.monotonic() - t_step
                print(f"{_ts()}  FAIL {step_name} (exit {e.code}, {elapsed:.1f}s)", flush=True)
                sys.exit(e.code)
        except Exception as e:
            elapsed = time.monotonic() - t_step
            print(f"{_ts()}  FAIL {step_name}: {e} ({elapsed:.1f}s)", flush=True)
            sys.exit(1)

    total = time.monotonic() - t_pipeline
    print(f"\nPipeline complete. ({total:.1f}s)")


def main():
    parser = argparse.ArgumentParser(description="Run the full pipeline")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM provider")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()
    run_pipeline(args.config, mock=args.mock, yes=args.yes)


if __name__ == "__main__":
    main()
