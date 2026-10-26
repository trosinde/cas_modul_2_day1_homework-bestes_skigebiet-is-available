# Spec Delta

## ADDED Requirements

### Requirement: Pipeline Timestamps
The system SHALL prefix every pipeline step output line (RUN, OK, FAIL, SKIP) with a `[HH:MM:SS]` local-time timestamp and append the step duration to OK and FAIL lines.

#### Scenario: Timestamp on RUN
- **WHEN** a pipeline step starts
- **THEN** print `[HH:MM:SS]  RUN  {step_name}`

#### Scenario: Duration on OK
- **WHEN** a pipeline step completes successfully
- **THEN** print `[HH:MM:SS]  OK   {step_name} ({duration}s)`

#### Scenario: Duration on FAIL
- **WHEN** a pipeline step fails
- **THEN** print `[HH:MM:SS]  FAIL {step_name} ({duration}s)`

#### Scenario: Total pipeline duration
- **WHEN** the pipeline finishes (all steps done or after a failure)
- **THEN** print `Pipeline complete. ({total_duration}s)` with the wall-clock time from first step to last

### Requirement: Component Progress Summary
Every component SHALL print a one-line summary to stdout during its `run()` execution so the user can see what happened in each step.

#### Scenario: C2 gastro_source fallback summary
- **WHEN** gastro_source runs with menu scraping disabled
- **THEN** print a summary showing total restaurant count and number of countries with fallback prices

#### Scenario: C3 geo_matcher summary
- **WHEN** geo_matcher completes matching
- **THEN** print a summary showing matched, ambiguous, and unmatched counts

#### Scenario: C4 cost_model summary
- **WHEN** cost_model finishes computing costs
- **THEN** print a summary showing total resorts computed and number in the ranking

#### Scenario: C5 clustering summary
- **WHEN** clustering completes
- **THEN** print a summary showing best k, silhouette score, and number of clusters

#### Scenario: C6 dashboard summary
- **WHEN** dashboard finishes
- **THEN** print a summary showing number of figures exported

#### Scenario: C7 validator summary
- **WHEN** validator completes in sample mode
- **THEN** print a summary showing number of fact-check entries generated
- **WHEN** validator completes in validate mode
- **THEN** print a summary showing recommendation and number of flags
