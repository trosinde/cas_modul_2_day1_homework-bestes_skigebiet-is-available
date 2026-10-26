"""C8: Build final PDF report and deploy dashboard."""

import shutil
from pathlib import Path

from common.log import get_logger

logger = get_logger("report_builder")

REPORT_TEMPLATE = """\
---
title: "Bestes Skigebiet für Familien – LLM-generierter Datensatz"
author: "Thorsten Rosin"
date: "2026"
geometry: margin=2cm
fontsize: 11pt
---

# Task 1: Fall und Zieldefinition

{task1}

# Task 2: Pipeline-Beschreibung

{task2}

# Task 3: Attribute und Prompting

{task3}

# Task 4: Visuelle Exploration

{task4}

# Task 5: Validierung

{task5}

# Task 6: Reflexion und Vision

{task6}

---

**Repository:** https://github.com/trosinde/cas_modul_2_day1_homework-bestes_skigebiet-is-available

**Dashboard:** https://trosinde.github.io/cas_modul_2_day1_homework-bestes_skigebiet-is-available/
"""


def read_task_text(task_dir: str, filename: str) -> str:
    """Read a task markdown file."""
    path = Path(task_dir) / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"*{filename} noch nicht geschrieben.*"


def build_report_md(cfg: dict) -> str:
    """Assemble report markdown from task files."""
    task1 = read_task_text("task1_case_definition", "case.md")
    task2 = read_task_text("task2_pipeline", "pipeline.md")
    task3 = read_task_text("task3_attributes_prompting", "attributes.md")
    task4 = read_task_text("task4_visual_exploration", "findings.md")
    task5_decision = read_task_text("task5_validation", "decision.md")
    task5_plan = read_task_text("task5_validation", "validation_plan.md")
    task5 = task5_plan + "\n\n" + task5_decision
    task6 = read_task_text("task6_reflection", "reflection.md")

    return REPORT_TEMPLATE.format(
        task1=task1,
        task2=task2,
        task3=task3,
        task4=task4,
        task5=task5,
        task6=task6,
    )


def copy_dashboard(cfg: dict):
    """Copy dashboard to docs/ for GitHub Pages."""
    src = Path("task4_visual_exploration") / "output" / "dashboard.html"
    dst = Path("docs") / "index.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        logger.info(f"Dashboard copied to {dst}")
    else:
        logger.warning(f"Dashboard not found at {src}")


def build_pdf(report_md_path: Path, pdf_path: Path, figures_dir: Path):
    """Build PDF from markdown using pandoc."""
    import subprocess

    cmd = [
        "pandoc",
        str(report_md_path),
        "-o",
        str(pdf_path),
        "--pdf-engine=xelatex",
        f"--resource-path={figures_dir.parent}",
        "--toc",
        "--number-sections",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"PDF built: {pdf_path}")
    except FileNotFoundError:
        logger.warning("pandoc not found, skipping PDF generation")
    except subprocess.CalledProcessError as e:
        logger.warning(f"PDF generation failed: {e.stderr}")


def run(cfg: dict):
    report_dir = Path(cfg.get("report_dir", "report"))
    report_dir.mkdir(parents=True, exist_ok=True)

    report_md = build_report_md(cfg)
    md_path = report_dir / "report.md"
    md_path.write_text(report_md, encoding="utf-8")

    pdf_path = report_dir / "report.pdf"
    figures_dir = report_dir / "figures"
    build_pdf(md_path, pdf_path, figures_dir)

    copy_dashboard(cfg)

    logger.info("Report build complete")
