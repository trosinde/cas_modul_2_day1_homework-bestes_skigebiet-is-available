import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jsonschema import validate


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_schema(schema_id, contracts_dir="contracts"):
    schema_path = Path(contracts_dir) / f"{schema_id}.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def _validate(data, schema_id, contracts_dir="contracts"):
    schema = _load_schema(schema_id, contracts_dir)
    if isinstance(data, list):
        for row in data:
            validate(instance=row, schema=schema)
    else:
        validate(instance=data, schema=schema)


def _write_meta(output_path, schema_id, schema_version, produced_by,
                config_path="config.yaml", inputs=None, row_count=None):
    meta = {
        "schema_id": schema_id,
        "schema_version": schema_version,
        "produced_by": produced_by,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config_sha256": _file_sha256(config_path) if Path(config_path).exists() else "",
        "inputs": [],
    }
    if inputs:
        for p in inputs:
            p = Path(p)
            meta["inputs"].append({
                "path": str(p),
                "sha256": _file_sha256(p) if p.exists() else "",
            })
    if row_count is not None:
        meta["row_count"] = row_count

    meta_path = Path(str(output_path) + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def _row_to_typed(row, schema):
    props = schema.get("properties", {})
    typed = {}
    for col, val in row.items():
        if val == "" or val is None or (isinstance(val, float) and pd.isna(val)):
            typed[col] = None
            continue
        prop = props.get(col, {})
        ptypes = prop.get("type", "string")
        if isinstance(ptypes, list):
            ptypes = [t for t in ptypes if t != "null"]
            ptype = ptypes[0] if ptypes else "string"
        else:
            ptype = ptypes
        if ptype == "number":
            typed[col] = float(val)
        elif ptype == "integer":
            typed[col] = int(float(val))
        elif ptype == "boolean":
            typed[col] = val if isinstance(val, bool) else str(val).lower() in ("true", "1")
        else:
            typed[col] = val
    return typed


def read_csv(path, schema_id, contracts_dir="contracts"):
    path = Path(path)
    schema = _load_schema(schema_id, contracts_dir)
    df = pd.read_csv(path, encoding="utf-8")
    for _, row in df.iterrows():
        typed = _row_to_typed(row.to_dict(), schema)
        validate(instance=typed, schema=schema)
    return df


def write_csv(df, path, schema_id, produced_by, config_path="config.yaml",
              inputs=None, contracts_dir="contracts", schema_version="1.0.0"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = _load_schema(schema_id, contracts_dir)
    col_order = schema.get("x-column-order", list(df.columns))
    cols = [c for c in col_order if c in df.columns]
    remaining = [c for c in df.columns if c not in cols]
    df = df[cols + remaining]

    for _, row in df.iterrows():
        typed = _row_to_typed(row.to_dict(), schema)
        validate(instance=typed, schema=schema)

    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    _write_meta(path, schema_id, schema_version, produced_by,
                config_path, inputs, row_count=len(df))


def read_json(path, schema_id, contracts_dir="contracts"):
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _validate(data, schema_id, contracts_dir)
    return data


def write_json(data, path, schema_id, produced_by, config_path="config.yaml",
               inputs=None, contracts_dir="contracts", schema_version="1.0.0"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _validate(data, schema_id, contracts_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    row_count = None
    if isinstance(data, dict) and "checks" in data:
        row_count = len(data["checks"])
    _write_meta(path, schema_id, schema_version, produced_by,
                config_path, inputs, row_count=row_count)
