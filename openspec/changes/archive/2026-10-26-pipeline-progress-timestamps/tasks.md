# Tasks

- [x] Add timestamps and duration to pipeline runner (`pipeline/run_pipeline.py`): import `time` and `datetime`, add `_ts()` helper returning `[HH:MM:SS]`, record `t_pipeline` at start, record `t_step` before each step, print `{_ts()}  RUN  {step_name}`, print `{_ts()}  OK   {step_name} ({duration:.1f}s)` / FAIL / SKIP with timestamp, print `Pipeline complete. ({total:.1f}s)` at end
- [x] Add summary print to C3 geo_matcher (`components/geo_matcher/core.py`): after line ~169 (logger.info), add `print(f"  {n_matched} matched, {n_ambiguous} ambiguous, {n_unmatched} unmatched")`
- [x] Add summary print to C4 cost_model (`components/cost_model/core.py`): after line ~169 (logger.info), add `print(f"  {len(costs_df)} Skigebiete berechnet, {in_rank} im Ranking")`
- [x] Add summary print to C5 clustering (`components/clustering/core.py`): after line ~249 (logger.info), add `print(f"  Best k={meta_extra['best_k']} (silhouette {meta_extra['silhouette_scores'][meta_extra['best_k']]:.2f}) — {clusters_df['cluster_id'].nunique()} Cluster")`
- [x] Add summary print to C6 dashboard (`components/dashboard/core.py`): after line ~186 (logger.info), add `print(f"  Dashboard + {len(figures_df)} Figures exportiert")`
- [x] Add summary print to C7 validator (`components/validator/core.py`): in `run_sample()` after line ~405 add `print(f"  Fact-check sample: {len(sample)} Einträge")`, in `run_validate()` after line ~496 add `print(f"  Validation: {report['recommendation']} ({len(all_flags)} Flags)")`
- [x] Add fallback summary print to C2 gastro_source (`components/gastro_source/core.py`): in `run()` when `not scrape_menus`, after applying country fallback, add `print(f"  {len(restaurants)} Restaurants | Fallback-Preise für {len(set(r['country'] for r in restaurants))} Länder")`
- [x] Verify: run `make mock-all` and confirm every step shows `[HH:MM:SS]` timestamps, duration on OK lines, a summary line, and total pipeline duration
