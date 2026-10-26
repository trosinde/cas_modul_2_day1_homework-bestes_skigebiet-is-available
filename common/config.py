import json
from pathlib import Path

import yaml
from jsonschema import validate, ValidationError


def load(path="config.yaml", contracts_dir="contracts"):
    cfg_path = Path(path)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    schema_path = Path(contracts_dir) / "config.schema.json"
    if schema_path.exists():
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        validate(instance=cfg, schema=schema)

    return cfg
