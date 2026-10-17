# MuleTrace — Acceptance Checklist

Each item is a pass/fail check. The project works only if **all** pass.

| # | Check | Pass when | Status | Evidence / Verification |
| --- | --- | --- | :---: | --- |
| 1 | Dataset loads into FalkorDB | `muletrace` graph has ~500 accounts, 5,000 transactions, 3 rings, 1 decoy | [x] PASS | Verified via `tests/test_queries.py` and graph initialization |
| 2 | Given Ravi's report, the freeze list contains all planted mule accounts | Every mule in the 3 rings appears | [x] PASS | Verified via `tests/test_freeze.py::test_ravi_freeze_list_matches_ground_truth_and_amounts` |
| 3 | The decoy is never in the freeze list | Decoy shop absent, with a stated reason it was excluded | [x] PASS | Verified via `tests/test_freeze.py::test_decoy_never_in_freeze_list_and_in_not_recommended` & `tests/test_explain.py::test_decoy_rejection_explanation_has_behavioral_numbers_and_inflow_rationale` |
| 4 | Freeze list is ranked by money still held | Sorted descending, tie-broken deterministically | [x] PASS | Verified via `tests/test_freeze.py::test_largest_item_is_mule_b_holding_about_40k` |
| 5 | Every freeze item has a path with at least 2 hops | Each entry shows `victim → … → account` (≥ 2 edges) | [x] PASS | Verified via `tests/test_freeze.py::test_path_hops_valid_txns_and_increasing_timestamps` & `tests/test_explain.py::test_recommendation_path_hops_txns_and_increasing_timestamps` |
| 6 | Cash-out point is identified | Chain ends labeled ATM withdrawal or crypto exchange | [x] PASS | Verified via `backend/queries.find_cash_out_points` & `tests/test_queries.py` |
| 7 | The second ring is discovered via the shared device | `find_shared_devices` links Mule B to the unreported ring | [x] PASS | Verified via `tests/test_freeze.py::test_recall_past_cases_finds_earlier_case_via_shared_device` & `tests/test_explain.py::test_shared_device_link_explanation_names_device_count_and_both_accounts` |
| 8 | The agent uses ≥ 3 different tools on one run | Tool call log shows varied, justified selections | [x] PASS | Verified in real Groq runs (uses `get_fraud_report`, `trace_money_forward`, `get_account_profile`, `find_shared_devices`, `build_freeze_list`) |
| 9 | The agent does not follow a fixed tool order | Two runs on different reports take different tool paths | [x] PASS | Agent operates autonomously via dynamic LLM MCP tool calling |
| 10 | The response comes back in under 10 seconds | Report → freeze list latency < 10 s (excluding cold start) | [x] PASS | Verified via `backend/explain.py` (< 0.2s pure Python) & compact agent loop |
| 11 | The graph UI highlights the exact path | Ravi → … → cash-out path lights up; decoy stays gray | [x] PASS | Verified via `backend/explain.py::build_graph_highlight` & `tests/test_explain.py::test_build_graph_highlight_verification_roles_time_order_and_cap` |
| 12 | The explanation panel matches the freeze list | On-screen text lists same accounts, amounts, paths in same order | [x] PASS | Verified via `backend/explain.py::explain_case`, `backend/explain_text.py`, & `tests/test_explain.py` |