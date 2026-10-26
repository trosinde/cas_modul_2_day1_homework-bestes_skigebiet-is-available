.PHONY: all resorts gastro match costs cluster dashboard sample validate report \
       mock-all test test-contracts test-llm-gateway test-resort-source test-gastro-source \
       test-geo-matcher test-cost-model test-clustering test-dashboard test-validator \
       resorts-test gastro-test

PYTHON ?= python3
CONFIG ?= config.yaml

# --- Full pipeline ---
all:
	$(PYTHON) -m pipeline.run_pipeline --config $(CONFIG)

# --- Individual components ---
resorts:
	$(PYTHON) -m components.resort_source --config $(CONFIG)

gastro:
	$(PYTHON) -m components.gastro_source --config $(CONFIG)

match:
	$(PYTHON) -m components.geo_matcher --config $(CONFIG)

costs:
	$(PYTHON) -m components.cost_model --config $(CONFIG)

cluster:
	$(PYTHON) -m components.clustering --config $(CONFIG)

dashboard:
	$(PYTHON) -m components.dashboard --config $(CONFIG)

sample:
	$(PYTHON) -m components.validator --config $(CONFIG) --mode sample

validate:
	$(PYTHON) -m components.validator --config $(CONFIG) --mode validate

report:
	$(PYTHON) -m components.report_builder --config $(CONFIG)

# --- Test batch (1 batch only) ---
resorts-test:
	$(PYTHON) -m components.resort_source --config $(CONFIG) --limit-batches 1

gastro-test:
	$(PYTHON) -m components.gastro_source --config $(CONFIG) --limit-batches 1

# --- Mock pipeline (no API cost) ---
mock-all:
	$(PYTHON) -m pipeline.run_pipeline --config $(CONFIG) --mock --yes

# --- Tests ---
test: test-contracts test-llm-gateway test-resort-source test-cost-model test-clustering test-dashboard test-validator

test-contracts:
	$(PYTHON) -m pytest tests/contract/ -v

test-llm-gateway:
	$(PYTHON) -m pytest components/llm_gateway/tests/ -v

test-resort-source:
	$(PYTHON) -m pytest components/resort_source/tests/ -v

test-gastro-source:
	$(PYTHON) -m pytest components/gastro_source/tests/ -v

test-geo-matcher:
	$(PYTHON) -m pytest components/geo_matcher/tests/ -v

test-cost-model:
	$(PYTHON) -m pytest components/cost_model/tests/ -v

test-clustering:
	$(PYTHON) -m pytest components/clustering/tests/ -v

test-dashboard:
	$(PYTHON) -m pytest components/dashboard/tests/ -v

test-validator:
	$(PYTHON) -m pytest components/validator/tests/ -v
