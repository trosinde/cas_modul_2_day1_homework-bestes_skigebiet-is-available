# Dashboard (C6) Specification

## Purpose

Generates an interactive HTML dashboard and PNG figures for the report. Reads cost and cluster data, produces `task4_visual_exploration/output/dashboard.html` and figures in `report/figures/`.

## Requirements

### Requirement: Interactive Dashboard
The system SHALL generate an HTML dashboard with interactive map, table, and charts.

#### Scenario: Map view
- **WHEN** rendering the dashboard
- **THEN** show resorts on an OpenStreetMap tile map with color-coded markers by cluster

#### Scenario: Sortable table
- **WHEN** rendering the resort table
- **THEN** include tooltips and sorting for all key columns

#### Scenario: Figures export
- **WHEN** generating the dashboard
- **THEN** also export PNG figures to `report/figures/` with naming pattern `fig_{component}_{description}.png`

#### Scenario: Data quality annotation on country boxplot
- **WHEN** rendering the "Tageskosten je Land" boxplot
- **AND** a country has more than 50% of its resorts with estimated prices (source_prices starting with "estimated")
- **THEN** display a warning annotation "⚠ X% geschätzt" below that country's box

#### Scenario: Challenge score filter
- **WHEN** the user moves the "Min. Anspruch" slider in the sidebar
- **THEN** only resorts with `challenge_score >= slider value` appear in the Top-10 table, map markers, and all charts
- **AND** the current slider value is shown next to the slider

#### Scenario: Challenge score cell tooltip
- **WHEN** hovering over a resort's Anspruch value in the Top-10 table
- **THEN** a tooltip shows the km breakdown: "Blau: X km · Rot: Y km · Schwarz: Z km"

#### Scenario: Challenge score column tooltip
- **WHEN** hovering over the "Anspruch" column header info icon
- **THEN** a tooltip explains what the score means for the user: higher = more challenging terrain, based on the share of intermediate and advanced runs, variety of difficulty levels, and resort size
- **AND** the tooltip does NOT show the internal formula weights or variable names

### Requirement: Figures Index
The system SHALL write `report/figures/figures_index.csv` conforming to `contracts/figures_index.schema.json`.

#### Scenario: Index fields
- **WHEN** writing the index
- **THEN** include: file, component, title, task (1–6), caption
