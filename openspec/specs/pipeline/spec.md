# Pipeline Specification

## Purpose

Orchestrates the full data pipeline from source fetching through validation. Defines execution order, Make targets, mock mode, and shared infrastructure (LLM gateway, merge log, meta envelopes).

## Requirements

### Requirement: Component Execution Order
The system SHALL run components in this fixed order: C1 (resort_source) → C2 (gastro_source) → C3 (geo_matcher) → C4 (cost_model) → C5 (clustering) → C6 (dashboard) → C7 (validator).

#### Scenario: Always-run components
- **WHEN** running the pipeline
- **THEN** always run C1, C4, C5, C6, C7

#### Scenario: Conditional gastro components
- **WHEN** `include_lunch_cost` is false and no prior gastro data exists
- **THEN** skip C2 and C3

### Requirement: Make Targets
The system SHALL provide Make targets for running individual components and the full pipeline.

#### Scenario: Full pipeline
- **WHEN** user runs `make all`
- **THEN** run the full pipeline with real LLM

#### Scenario: Mock pipeline
- **WHEN** user runs `make mock-all`
- **THEN** run with `provider=mock`, `min_items=3`, `limit_batches=1`

#### Scenario: Test batch
- **WHEN** user runs `make resorts-test`
- **THEN** run C1 with `--limit-batches 1` (one LLM batch only)

#### Scenario: Clean targets
- **WHEN** user runs `make resorts-clean`
- **THEN** remove all C1 caches (openskidata, osm, osrm, scraper, ratings) and processed outputs

#### Scenario: Test targets
- **WHEN** user runs `make test`
- **THEN** run pytest for all component test suites and contract validation tests

### Requirement: LLM Gateway
The system SHALL provide a single LLM gateway for all LLM calls, supporting multiple providers.

#### Scenario: Provider detection
- **WHEN** `llm.provider` is `auto`
- **THEN** detect from environment variables (ANTHROPIC_API_KEY or OPENAI_API_KEY); fail if both or neither are set

#### Scenario: Mock provider
- **WHEN** `llm.provider` is `mock`
- **THEN** read responses from `contracts/examples/llm_responses/{template_id}.json`

#### Scenario: Response envelope
- **WHEN** an LLM call completes
- **THEN** save the full envelope to `out_path` conforming to `contracts/llm_envelope.schema.json`: kind, template_id, timestamp, provider, model, temperature, tokens, records, raw_response, attempts, error

#### Scenario: Record validation
- **WHEN** LLM returns records
- **THEN** validate each against the specified `record_schema_id`; discard invalid records

### Requirement: Merge Log
The system SHALL log all merge anomalies to `*_merge_log.csv` conforming to `contracts/merge_log.schema.json`.

#### Scenario: Anomaly types
- **WHEN** a record fails during merging
- **THEN** log it with reason: schema_violation, unknown_item, duplicate, or parse_failed

#### Scenario: Log fields
- **WHEN** writing a merge log entry
- **THEN** include: batch_id, item_id, record_name, reason, detail

### Requirement: Meta Files
The system SHALL write a `.meta.json` sidecar for every output CSV.

#### Scenario: Meta content
- **WHEN** writing a `.meta.json` file
- **THEN** include: producer, timestamp, schema_id, row_count, and input file paths

### Requirement: Configuration
The system SHALL read all parameters from `config.yaml`. No hard-coded paths, models, or numeric thresholds in component code.

#### Scenario: Required config sections
- **WHEN** loading config
- **THEN** expect sections: origin, family, resorts, gastro, matching, costs, quality, clustering, llm, acceptance

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
