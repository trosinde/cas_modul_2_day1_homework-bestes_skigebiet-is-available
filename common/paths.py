from pathlib import Path


def data_dir(cfg):
    return Path(cfg.get("data_dir", "data"))


def raw_dir(cfg, component):
    return data_dir(cfg) / "raw" / component


def processed_dir(cfg):
    return data_dir(cfg) / "processed"


def log_dir(cfg):
    return Path(cfg.get("log_dir", "logs"))


def report_dir(cfg):
    return Path(cfg.get("report_dir", "report"))


def figures_dir(cfg):
    return report_dir(cfg) / "figures"
