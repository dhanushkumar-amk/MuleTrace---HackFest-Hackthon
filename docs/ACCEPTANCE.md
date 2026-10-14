# MuleTrace — Acceptance Checklist

Each item is a pass/fail check. The project works only if **all** pass.

| # | Check | Pass when |
| --- | --- | --- |
| 1 | Dataset loads into FalkorDB | `muletrace` graph has ~500 accounts, 5,000 transactions, 3 rings, 1 decoy |
| 2 | Given Ravi's report, the freeze list contains all planted mule accounts | Every mule in the 3 rings appears |
| 3 | The decoy is never in the freeze list | Decoy shop absent, with a stated reason it was excluded |
| 4 | Freeze list is ranked by money still held | Sorted descending, tie-broken deterministically |
| 5 | Every freeze item has a path with at least 2 hops | Each entry shows `victim → … → account` (≥ 2 edges) |
| 6 | Cash-out point is identified | Chain ends labeled ATM withdrawal or crypto exchange |
| 7 | The second ring is discovered via the shared device | `find_shared_devices` links Mule B to the unreported ring |
| 8 | The agent uses ≥ 3 different tools on one run | Tool call log shows varied, justified selections |
| 9 | The agent does not follow a fixed tool order | Two runs on different reports take different tool paths |
| 10 | The response comes back in under 10 seconds | Report → freeze list latency < 10 s (excluding cold start) |
| 11 | The graph UI highlights the exact path | Ravi → … → cash-out path lights up; decoy stays gray |
| 12 | The explanation panel matches the freeze list | On-screen text lists same accounts, amounts, paths in same order |