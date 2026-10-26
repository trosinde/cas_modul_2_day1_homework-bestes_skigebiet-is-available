"""C5: k-Means clustering with PCA."""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, silhouette_samples

from common.contract_io import read_csv, write_csv
from common.log import get_logger

logger = get_logger("clustering")

CLUSTER_LABELS = {
    0: "nah & günstig",
    1: "gross & teuer",
    2: "familienfreundlich",
    3: "schneesicher & abgelegen",
    4: "klein & preiswert",
    5: "Premium-Gebiete",
    6: "Allrounder",
    7: "Budget-Gebiete",
}


def find_best_k(X: np.ndarray, k_min: int, k_max: int, random_state: int) -> tuple[int, dict]:
    """Find best k via silhouette score."""
    scores = {}
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(X)
        s = silhouette_score(X, labels)
        scores[k] = round(s, 4)
    best_k = max(scores, key=scores.get)
    return best_k, scores


def assign_cluster_labels(df: pd.DataFrame, features: list[str]) -> dict[int, str]:
    """Assign descriptive labels based on cluster centroids."""
    labels = []
    for cid in sorted(df["cluster_id"].unique()):
        cluster = df[df["cluster_id"] == cid]
        if len(cluster) == 0:
            labels.append((cid, f"Cluster {cid}"))
            continue

        mean_cost = cluster["family_day_cost_eur"].mean() if "family_day_cost_eur" in cluster.columns else 0
        mean_quality = cluster["quality_score"].mean() if "quality_score" in cluster.columns else 0
        mean_drive = cluster["drive_time_min"].mean() if "drive_time_min" in cluster.columns else 0

        if mean_cost < df["family_day_cost_eur"].median() and mean_drive < df["drive_time_min"].median():
            label = "nah & günstig"
        elif mean_quality > df["quality_score"].quantile(0.75):
            label = "Premium-Gebiete"
        elif mean_cost > df["family_day_cost_eur"].quantile(0.75):
            label = "gross & teuer"
        elif "family_friendliness" in cluster.columns and cluster["family_friendliness"].mean() > df["family_friendliness"].quantile(0.75):
            label = "familienfreundlich"
        elif "snow_reliability" in cluster.columns and cluster["snow_reliability"].mean() > df["snow_reliability"].quantile(0.75):
            label = "schneesicher & abgelegen"
        else:
            label = CLUSTER_LABELS.get(cid, f"Cluster {cid}")
        labels.append((cid, label))

    return dict(labels)


def run_clustering(costs_df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Run k-means clustering on resort cost data."""
    cluster_cfg = cfg["clustering"]
    features = cluster_cfg["features"]
    k_min = cluster_cfg["k_min"]
    k_max = cluster_cfg["k_max"]
    random_state = cluster_cfg["random_state"]

    available = [f for f in features if f in costs_df.columns]
    X_raw = costs_df[available].copy()
    X_raw = X_raw.fillna(X_raw.median())

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    effective_k_max = min(k_max, len(costs_df) - 1)
    best_k, sil_scores = find_best_k(X_scaled, k_min, effective_k_max, random_state)
    logger.info(f"Best k={best_k}, silhouette scores: {sil_scores}")

    km = KMeans(n_clusters=best_k, random_state=random_state, n_init=10)
    labels = km.fit_predict(X_scaled)

    pca = PCA(n_components=2, random_state=random_state)
    coords = pca.fit_transform(X_scaled)

    sil_values = silhouette_samples(X_scaled, labels)

    result = pd.DataFrame({
        "resort_id": costs_df["resort_id"].values,
        "cluster_id": labels,
        "cluster_label": "",
        "pc1": coords[:, 0].round(4),
        "pc2": coords[:, 1].round(4),
        "silhouette": sil_values.round(4),
    })

    temp = costs_df.copy()
    temp["cluster_id"] = labels
    label_map = assign_cluster_labels(temp, available)
    result["cluster_label"] = result["cluster_id"].map(label_map)

    meta_extra = {
        "best_k": best_k,
        "features": available,
        "silhouette_scores": sil_scores,
    }
    return result, meta_extra


def run(cfg: dict):
    from common.paths import processed_dir

    proc = processed_dir(cfg)
    costs_df = read_csv(Path(proc) / "resorts_costs.csv", "cost_table")
    clusters_df, meta_extra = run_clustering(costs_df, cfg)

    write_csv(
        clusters_df,
        Path(proc) / "clusters.csv",
        "clusters",
        "clustering@1.0.0",
        inputs=[str(Path(proc) / "resorts_costs.csv")],
    )
    logger.info(
        f"Clustered {len(clusters_df)} resorts into "
        f"{clusters_df['cluster_id'].nunique()} clusters"
    )
