# Spec Delta

## ADDED Requirements

### Requirement: Progress Display
The system SHALL show menu extraction progress with both the website-count and total restaurant count.

#### Scenario: Progress format during extraction
- **WHEN** extracting menu prices from restaurants with websites
- **THEN** display progress as `[X%] N/M mit Website | T gesamt | menu:A fallback:B err:C | ETA Xs | name` where M = restaurants with website, T = all restaurants, and the percentage refers to M

#### Scenario: Completion summary
- **WHEN** menu extraction finishes
- **THEN** display a summary including both counts: `M mit Website von T gesamt`
