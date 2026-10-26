# Spec Delta

## MODIFIED Requirements

### Requirement: Interactive Dashboard

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
