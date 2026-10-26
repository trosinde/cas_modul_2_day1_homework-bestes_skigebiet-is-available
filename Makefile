.PHONY: all resorts gastro gastro-scrape match costs cluster dashboard sample validate report \
       mock-all clean clean-all resorts-clean gastro-clean match-clean costs-clean \
       cluster-clean dashboard-clean report-clean \
       test test-contracts test-llm-gateway test-resort-source \
       test-gastro-source test-geo-matcher test-cost-model test-clustering test-dashboard \
       test-validator resorts-test gastro-test

PYTHON ?= .venv/bin/python
CONFIG ?= config.yaml
MENU_LIMIT ?=

# --- Full pipeline ---
all:
	$(PYTHON) -m pipeline.run_pipeline --config $(CONFIG)

# --- Individual components ---
resorts:
	$(PYTHON) -m components.resort_source --config $(CONFIG)

gastro:
	$(PYTHON) -m components.gastro_source --config $(CONFIG) $(if $(MENU_LIMIT),--menu-limit $(MENU_LIMIT))

gastro-scrape:
	$(PYTHON) -m components.gastro_source --config $(CONFIG) --scrape-menus $(if $(MENU_LIMIT),--menu-limit $(MENU_LIMIT))

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
	$(PYTHON) -m components.gastro_source --config $(CONFIG) --scrape-menus --menu-limit 5

# --- Clean: per component and full pipeline ---
resorts-clean:
	rm -rf data/raw/resort_source/openskidata/ data/raw/resort_source/osm/ data/raw/resort_source/osrm/ data/raw/resort_source/scraper/
	rm -rf data/raw/resort_source/resort_ratings_run*/
	rm -f data/processed/resorts.csv data/processed/resorts.csv.meta.json
	rm -f data/processed/resorts_runs.csv data/processed/resorts_merge_log.csv
	rm -f data/processed/scraping_report.csv
	@echo "C1 resort_source caches cleared."

gastro-clean:
	rm -rf data/raw/gastro_source/
	rm -f data/processed/restaurants.csv data/processed/restaurants.csv.meta.json
	rm -f data/processed/restaurants_runs.csv data/processed/restaurants_merge_log.csv
	@echo "C2 gastro_source caches cleared."

match-clean:
	rm -f data/processed/matches.csv data/processed/matches.csv.meta.json
	rm -f data/processed/resort_lunch.csv data/processed/resort_lunch.csv.meta.json
	@echo "C3 geo_matcher outputs cleared."

costs-clean:
	rm -f data/processed/resorts_costs.csv data/processed/resorts_costs.csv.meta.json
	@echo "C4 cost_model outputs cleared."

cluster-clean:
	rm -f data/processed/clusters.csv data/processed/clusters.csv.meta.json
	@echo "C5 clustering outputs cleared."

dashboard-clean:
	rm -f task4_visual_exploration/output/dashboard.html
	rm -f report/figures/fig_dashboard_*.png report/figures/fig_clustering_*.png
	rm -f report/figures/fig_data_provenance.png
	rm -f report/figures/figures_index.csv report/figures/figures_index.csv.meta.json
	@echo "C6 dashboard outputs cleared."

report-clean:
	rm -rf report/output/
	@echo "Report outputs cleared."

clean-all: resorts-clean gastro-clean match-clean costs-clean cluster-clean dashboard-clean report-clean
	@echo "All pipeline outputs cleared."

clean: costs-clean cluster-clean dashboard-clean
	@echo "Downstream outputs (C4-C6) cleared. Raw data preserved."

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
