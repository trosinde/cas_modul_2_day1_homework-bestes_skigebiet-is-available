# Clustering (C5) Specification

## Purpose

Groups resorts into clusters using K-Means on standardized features, with automatic k selection via silhouette score. Produces `data/processed/clusters.csv` conforming to `contracts/clusters.schema.json`.

## Requirements

### Requirement: Feature-Based Clustering
The system SHALL cluster resorts using the features defined in `config.clustering.features`.

#### Scenario: Feature list
- **WHEN** clustering
- **THEN** use features: quality_score, family_day_cost_eur, slope_km, snow_reliability, family_friendliness, drive_time_min

#### Scenario: Standardization
- **WHEN** preparing features
- **THEN** standardize all features to zero mean and unit variance

#### Scenario: K selection
- **WHEN** choosing k
- **THEN** test k from `clustering.k_min` (3) to `clustering.k_max` (8), select the k with highest mean silhouette score

### Requirement: Cluster Output
The system SHALL write `data/processed/clusters.csv` conforming to `contracts/clusters.schema.json`.

#### Scenario: PCA projection
- **WHEN** writing cluster rows
- **THEN** include pc1, pc2 from PCA(n_components=2) for visualization

#### Scenario: Cluster labels
- **WHEN** assigning cluster labels
- **THEN** generate descriptive labels based on cluster centroid characteristics

#### Scenario: Silhouette per resort
- **WHEN** writing a cluster row
- **THEN** include per-resort silhouette score (range -1 to 1)
