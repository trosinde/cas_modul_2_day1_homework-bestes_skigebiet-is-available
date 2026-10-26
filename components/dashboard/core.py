"""C6: Dashboard – single-page HTML with Leaflet map and Plotly.js charts."""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from jinja2 import Template
from common.contract_io import read_csv
from common.log import get_logger

logger = get_logger("dashboard")


def prepare_data(cfg: dict) -> dict:
    """Load all processed data for the dashboard."""
    from common.paths import processed_dir
    proc = Path(processed_dir(cfg))

    data = {}
    data["resorts"] = read_csv(proc / "resorts_costs.csv", "cost_table").to_dict("records")

    if (proc / "clusters.csv").exists():
        data["clusters"] = read_csv(proc / "clusters.csv", "clusters").to_dict("records")

    if (proc / "restaurants.csv").exists():
        data["restaurants"] = read_csv(proc / "restaurants.csv", "restaurant_table").to_dict("records")

    if (proc / "matches.csv").exists():
        data["matches"] = read_csv(proc / "matches.csv", "matches").to_dict("records")

    if (proc / "resort_lunch.csv").exists():
        data["resort_lunch"] = read_csv(proc / "resort_lunch.csv", "resort_lunch").to_dict("records")

    data["config"] = {
        "origin": cfg["origin"],
        "radius_km": cfg.get("matching", {}).get("radius_km", {}),
        "max_drive_time_min": cfg["costs"]["max_drive_time_min"],
        "include_lunch": cfg.get("include_lunch_cost", False),
    }

    return data


def clean_for_json(obj):
    """Replace NaN/None with null for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj) if not np.isnan(obj) else None
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def render_dashboard(data: dict) -> str:
    """Render the HTML dashboard from template."""
    template_path = Path(__file__).parent / "template.html"
    template = Template(template_path.read_text(encoding="utf-8"))

    clean_data = clean_for_json(data)

    return template.render(
        data_json=json.dumps(clean_data, ensure_ascii=False),
        title="Skigebiete Familien-Ranking",
    )


def export_figures(data: dict, figures_dir: Path, cfg: dict) -> pd.DataFrame:
    """Export chart PNGs for the report."""
    import plotly.graph_objects as go
    import plotly.express as px

    figures_dir.mkdir(parents=True, exist_ok=True)
    figures = []

    resorts = pd.DataFrame(data["resorts"])

    if len(resorts) > 0:
        ranked = resorts[resorts.get("in_ranking", pd.Series(dtype=bool)) == True] if "in_ranking" in resorts.columns else resorts
        fig = px.scatter(
            ranked,
            x="family_day_cost_eur", y="quality_score",
            size="slope_km", color="country",
            hover_name="name",
            labels={"family_day_cost_eur": "Tageskosten Familie (EUR)", "quality_score": "Qualitätsscore"},
            title="Tageskosten vs. Qualität",
        )
        path = figures_dir / "fig_dashboard_01_cost_vs_quality.png"
        fig.write_image(str(path), width=1600, height=1000)
        figures.append({"file": path.name, "component": "dashboard", "title": "Tageskosten vs. Qualität", "task": 4, "caption": "Jeder Punkt ist ein Skigebiet; Grösse = Pisten-km, Farbe = Land."})

    if "value_rank" in resorts.columns and resorts["value_rank"].notna().any():
        top15 = resorts.nsmallest(15, "value_rank")
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Skipässe", x=top15["name"], y=top15["family_pass_cost_eur"]))
        fig.add_trace(go.Bar(name="Fahrt", x=top15["name"], y=top15["travel_cost_eur"]))
        if top15["lunch_cost_eur"].notna().any():
            fig.add_trace(go.Bar(name="Mittagessen", x=top15["name"], y=top15["lunch_cost_eur"].fillna(0)))
        fig.update_layout(barmode="stack", title="Top 15 – Kostenaufschlüsselung",
                          yaxis_title="EUR", xaxis_tickangle=-45)
        path = figures_dir / "fig_dashboard_02_top15_costs.png"
        fig.write_image(str(path), width=1600, height=1000)
        figures.append({"file": path.name, "component": "dashboard", "title": "Top 15 Kostenaufschlüsselung", "task": 4, "caption": "Gestapelte Balken: Skipässe, Fahrtkosten und ggf. Mittagessen."})

    if len(resorts) > 0:
        fig = px.box(resorts, x="country", y="family_day_cost_eur",
                     title="Tageskosten je Land", labels={"family_day_cost_eur": "EUR", "country": "Land"})
        path = figures_dir / "fig_dashboard_03_costs_by_country.png"
        fig.write_image(str(path), width=1600, height=1000)
        figures.append({"file": path.name, "component": "dashboard", "title": "Tageskosten je Land", "task": 4, "caption": "Boxplot der Familien-Tageskosten nach Land."})

    if "clusters" in data and data["clusters"]:
        clusters = pd.DataFrame(data["clusters"])
        fig = px.scatter(clusters, x="pc1", y="pc2", color="cluster_label",
                         hover_data=["resort_id"],
                         title="PCA – Cluster", labels={"pc1": "PC1", "pc2": "PC2"})
        path = figures_dir / "fig_clustering_04_pca.png"
        fig.write_image(str(path), width=1600, height=1000)
        figures.append({"file": path.name, "component": "clustering", "title": "PCA mit Clustern", "task": 4, "caption": "k-Means-Cluster in der PCA-Projektion."})

    return pd.DataFrame(figures)


def run(cfg: dict):
    from common.paths import processed_dir
    from common.contract_io import write_csv

    data = prepare_data(cfg)

    html = render_dashboard(data)
    out_path = Path("task4_visual_exploration") / "output" / "dashboard.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    figures_dir = Path(cfg.get("report_dir", "report")) / "figures"
    figures_df = export_figures(data, figures_dir, cfg)
    if len(figures_df) > 0:
        write_csv(figures_df, figures_dir / "figures_index.csv", "figures_index", "dashboard@1.0.0")

    logger.info(f"Dashboard written to {out_path}, {len(figures_df)} figures exported")
