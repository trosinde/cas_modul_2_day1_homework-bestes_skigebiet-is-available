import logging
from pathlib import Path


def get_logger(component, log_dir="logs"):
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"skigebiete.{component}")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(log_path / f"{component}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s",
                                datefmt="%Y-%m-%dT%H:%M:%SZ")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger
