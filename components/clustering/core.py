"""C5: k-Means clustering with PCA."""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score, silhouette_samples
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from common.contract_io import read_csv, write_csv
from common.log import get_logger

logger = get_logger("clustering")


def _standardize(X: np.ndarray) -> np.ndarray:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    return (X - mean) / std


def _pca_2d(X: np.ndarray) -> np.ndarray:
    X_centered = X - X.mean(axis=0)
    cov = np.cov(X_centered, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    idx = np.argsort(eigenvalues)[::-1][:2]
    return X_centered @ eigenvectors[:, idx]


def _kmeans_simple(X: np.ndarray, k: int, random_state: int, n_init: int = 10) -> np.ndarray:
    from scipy.cluster.vq import kmeans2
    rng = np.random.RandomState(random_state)
    best_labels = None
    best_inertia = np.inf
    for _ in range(n_init):
        idx = rng.choice(len(X), k, replace=False)
        centroids, labels = kmeans2(X, X[idx], minit='matrix', iter=100)
        inertia = sum(np.linalg.norm(X[i] - centroids[labels[i]])**2 for i in range(len(X)))
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels
    return best_labels


def _silhouette_samples_simple(X: np.ndarray, labels: np.ndarray) -> np.ndarray:
    from scipy.spatial.distance import cdist
    n = len(X)
    unique_labels = np.unique(labels)
    if len(unique_labels) <= 1:
        return np.zeros(n)
    dist = cdist(X, X)
    sil = np.zeros(n)
    for i in range(n):
        same = labels == labels[i]
        same[i] = False
        if same.sum() == 0:
            sil[i] = 0
            continue
        a_i = dist[i, same].mean()
        b_i = np.inf
        for label in unique_labels:
            if label == labels[i]:
                continue
            other = labels == label
            if other.sum() > 0:
                b_i = min(b_i, dist[i, other].mean())
        sil[i] = (b_i - a_i) / max(a_i, b_i) if max(a_i, b_i) > 0 else 0
    return sil


def find_best_k(X: np.ndarray, k_min: int, k_max: int, random_state: int) -> tuple[int, dict]:
    scores = {}
    for k in range(k_min, k_max + 1):
        if HAS_SKLEARN:
            km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
            labels = km.fit_predict(X)
            s = silhouette_score(X, labels)
        else:
            labels = _kmeans_simple(X, k, random_state)
            sil = _silhouette_samples_simple(X, labels)
            s = float(sil.mean())
        scores[k] = round(s, 4)
    best_k = max(scores, key=scores.get)
    return best_k, scores


def assign_cluster_labels(df: pd.DataFrame, features: list[str]) -> dict[int, str]:
    """Assign a unique descriptive label to each cluster based on its profile."""
    medians = {
        "cost": df["family_day_cost_eur"].median() if "family_day_cost_eur" in df.columns else 0,
        "quality": df["quality_score"].median() if "quality_score" in df.columns else 0,
        "drive": df["drive_time_min"].median() if "drive_time_min" in df.columns else 0,
        "slope": df["slope_km"].median() if "slope_km" in df.columns else 0,
        "snow": df["snow_reliability"].median() if "snow_reliability" in df.columns else 0,
        "family": df["family_friendliness"].median() if "family_friendliness" in df.columns else 0,
    }

    profiles = []
    for cid in sorted(df["cluster_id"].unique()):
        c = df[df["cluster_id"] == cid]
        if len(c) == 0:
            profiles.append((cid, {}))
            continue
        def _mean(col):
            if col not in c.columns:
                return 0
            v = c[col].mean()
            return 0 if pd.isna(v) else v
        profiles.append((cid, {
            "cost": _mean("family_day_cost_eur"),
            "quality": _mean("quality_score"),
            "drive": _mean("drive_time_min"),
            "slope": _mean("slope_km"),
            "snow": _mean("snow_reliability"),
            "family": _mean("family_friendliness"),
        }))

    used_labels: set[str] = set()
    label_map: dict[int, str] = {}
    candidates = [
        lambda p: p["drive"] < medians["drive"] and p["cost"] < medians["cost"] and p["slope"] < medians["slope"],
        "nah & günstig (klein)",
        lambda p: p["drive"] < medians["drive"] and p["cost"] < medians["cost"] and p["slope"] >= medians["slope"],
        "nah & günstig (gross)",
        lambda p: p["slope"] > medians["slope"] * 2.5 and p["quality"] > medians["quality"],
        "Grosse Premium-Gebiete",
        lambda p: p["quality"] > medians["quality"] and p["snow"] > medians["snow"] and p["drive"] > medians["drive"],
        "schneesicher & hochwertig",
        lambda p: p["family"] > medians["family"] and p["quality"] > medians["quality"],
        "familienfreundlich",
        lambda p: p["slope"] < medians["slope"] and p["drive"] > medians["drive"] * 1.2,
        "kleine Ferngebiete",
        lambda p: p["cost"] > medians["cost"] and p["quality"] > medians["quality"],
        "Premium-Gebiete",
        lambda p: p["slope"] > medians["slope"] * 2.5,
        "grosse Skigebiete",
        lambda p: p["slope"] < medians["slope"] * 0.5,
        "Minigebiete",
        lambda p: p["drive"] > medians["drive"],
        "abgelegene Mittelgebiete",
    ]

    for cid, prof in profiles:
        if not prof:
            label_map[cid] = f"Cluster {cid}"
            continue
        assigned = False
        for i in range(0, len(candidates), 2):
            test_fn = candidates[i]
            label = candidates[i + 1]
            if label in used_labels:
                continue
            if test_fn(prof):
                label_map[cid] = label
                used_labels.add(label)
                assigned = True
                break
        if not assigned:
            label_map[cid] = f"Cluster {cid}"

    return label_map


def run_clustering(costs_df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    cluster_cfg = cfg["clustering"]
    features = cluster_cfg["features"]
    k_min = cluster_cfg["k_min"]
    k_max = cluster_cfg["k_max"]
    random_state = cluster_cfg["random_state"]

    available = [f for f in features if f in costs_df.columns]
    X_raw = costs_df[available].copy()
    X_raw = X_raw.fillna(X_raw.median())
    valid_mask = ~X_raw.isna().any(axis=1)

    if valid_mask.sum() == 0:
        logger.warning("All rows have NaN in clustering features, skipping")
        result = pd.DataFrame({
            "resort_id": costs_df["resort_id"].values,
            "cluster_id": -1,
            "cluster_label": "unbekannt",
            "pc1": 0.0,
            "pc2": 0.0,
            "silhouette": 0.0,
        })
        return result, {"best_k": 0, "features": available, "silhouette_scores": {}}

    if (~valid_mask).any():
        logger.warning("Dropping %d rows with NaN from clustering", (~valid_mask).sum())

    X_clean = X_raw[valid_mask]
    costs_clean = costs_df[valid_mask].reset_index(drop=True)

    if HAS_SKLEARN:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_clean)
    else:
        X_scaled = _standardize(X_clean.values)

    effective_k_max = min(k_max, len(costs_clean) - 1)
    effective_k_min = min(k_min, effective_k_max)
    if effective_k_min < 2:
        logger.warning("Too few resorts (%d) for clustering, skipping", len(costs_clean))
        result = pd.DataFrame({
            "resort_id": costs_df["resort_id"].values,
            "cluster_id": -1,
            "cluster_label": "unbekannt",
            "pc1": 0.0,
            "pc2": 0.0,
            "silhouette": 0.0,
        })
        return result, {"best_k": 0, "features": available, "silhouette_scores": {}}
    best_k, sil_scores = find_best_k(X_scaled, effective_k_min, effective_k_max, random_state)
    logger.info(f"Best k={best_k}, silhouette scores: {sil_scores}")

    if HAS_SKLEARN:
        km = KMeans(n_clusters=best_k, random_state=random_state, n_init=10)
        labels = km.fit_predict(X_scaled)
        pca = PCA(n_components=2, random_state=random_state)
        coords = pca.fit_transform(X_scaled)
        sil_values = silhouette_samples(X_scaled, labels)
    else:
        labels = _kmeans_simple(X_scaled, best_k, random_state)
        coords = _pca_2d(X_scaled)
        sil_values = _silhouette_samples_simple(X_scaled, labels)

    clustered = pd.DataFrame({
        "resort_id": costs_clean["resort_id"].values,
        "cluster_id": labels,
        "cluster_label": "",
        "pc1": np.round(coords[:, 0], 4),
        "pc2": np.round(coords[:, 1], 4),
        "silhouette": np.round(sil_values, 4),
    })

    temp = costs_clean.copy()
    temp["cluster_id"] = labels
    label_map = assign_cluster_labels(temp, available)
    clustered["cluster_label"] = clustered["cluster_id"].map(label_map)

    unclustered = pd.DataFrame({
        "resort_id": costs_df[~valid_mask]["resort_id"].values,
        "cluster_id": -1,
        "cluster_label": "unbekannt",
        "pc1": 0.0,
        "pc2": 0.0,
        "silhouette": 0.0,
    })
    result = pd.concat([clustered, unclustered], ignore_index=True)

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
    n_clusters = clusters_df["cluster_id"].nunique()
    best_k = meta_extra["best_k"]
    best_score = meta_extra["silhouette_scores"].get(best_k)
    logger.info(
        f"Clustered {len(clusters_df)} resorts into {n_clusters} clusters"
    )
    if best_score is not None:
        print(f"  Best k={best_k} (silhouette {best_score:.2f}) — {n_clusters} Cluster")
    else:
        print(f"  Kein Clustering möglich (fehlende Daten) — {n_clusters} Gruppe(n)")
