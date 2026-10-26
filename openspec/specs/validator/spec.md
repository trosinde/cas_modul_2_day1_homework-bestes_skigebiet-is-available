# Validator (C7) Specification

## Purpose

Validates pipeline output quality through fact-checking, consistency checks, and sensitivity analysis. Produces a validation report conforming to `contracts/validation_report.schema.json`.

## Requirements

### Requirement: Sample Generation
The system SHALL generate a random sample of resorts for manual fact-checking.

#### Scenario: Sample mode
- **WHEN** run with `mode=sample`
- **THEN** output a sample CSV with selected resorts and their key data for manual verification

### Requirement: Fact Check Accuracy
The system SHALL compare pipeline values against user-provided target values.

#### Scenario: Tolerance
- **WHEN** checking a numeric fact
- **THEN** accept if within `acceptance.fact_check_tolerance` (20%) of the target value

### Requirement: Consistency Checks
The system SHALL verify internal data consistency.

#### Scenario: Elevation sanity
- **WHEN** a resort has both base and top elevation
- **THEN** base_elevation_m < top_elevation_m

#### Scenario: Coordinate bounds
- **WHEN** checking coordinates
- **THEN** lat in [43, 49], lon in [4, 17] (Alpine region)

#### Scenario: Size class consistency
- **WHEN** checking size_class against slope_km
- **THEN** small < 30 km, medium 30–100 km, large > 100 km

### Requirement: Validation Report
The system SHALL produce `validation_report.json` conforming to `contracts/validation_report.schema.json`.

#### Scenario: Go/no-go recommendation
- **WHEN** all acceptance criteria pass
- **THEN** set `recommendation=go`
- **WHEN** some criteria fail but none are critical
- **THEN** set `recommendation=conditional_go`
- **WHEN** critical criteria fail
- **THEN** set `recommendation=no_go`
