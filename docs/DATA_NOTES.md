# DATA_NOTES — what was planted (Phase 5)

These are **demo-presenter notes only**. The agent never reads `docs/` or `tests/`;
nothing here (and nothing in `tests/ground_truth.json`) survives into the graph.

The base world (Phase 4) is ~460 normal accounts and ~5,000 normal transactions
over a 30-day window ending at `now`. Phase 5 plants **3 fraud rings**, a **decoy**,
and **1 fraud report** on top, using the reserved account range `ACC_0461..ACC_0500`.
The final world has **476 accounts / 5,110 transactions**. The answer key lives in
`tests/ground_truth.json`; the fraud report in `data/generated/fraud_reports.csv`.

## Ring 1 — the demo ring (reported)

- **Victim: Ravi Kumar** (`ACC_0461`), a normal account with salary + ordinary
  purchases before the fraud. Loses **Rs 85,000** to a fake-KYC call.
- Chain (completes in ~9.5 min, 2h before `now`):

  ```
  Ravi → A(ACC_0462) → B(ACC_0463)  [B HOLDS Rs 40,000]
                      → C(ACC_0464) → D(ACC_0465) → E(ACC_0466) → ATM (Rs 28,000)
  ```
  C keeps Rs 1,000, D keeps Rs 1,000, E keeps Rs 15,000 (the rest is cashed out).
- **Expected freeze list** (reachable >=2 hops from Ravi, ranked by `balance_held`):
  - `B` — **Rs 40,000** — Ravi → A → B
  - `E` — **Rs 15,000** — Ravi → A → C → D → E
  - `C` — Rs 1,000 — Ravi → A → C (tie with D, broken by id)
  - `D` — Rs 1,000 — Ravi → A → C → D
- **Cash-out:** `COP_001` (ATM, MG Road). `Mule B` (`ACC_0463`) shares `DEV_0593`
  with Ring 2 — the link `find_shared_devices` surfaces.
- **Report:** `FR_0001`, filed ~1h45m after the theft (trail still fresh).

## Ring 2 — the hidden ring (never reported)

- 5 mules (`ACC_0467..ACC_0471`), 4 days before `now`, funded with Rs 60,000 via a
  bank transfer, same fan-out feel, cashing out at `COP_016` (Kaleido Exchange).
- **`R2B` (`ACC_0468`) shares `DEV_0593` with `Mule B`.** No fraud report — only
  discoverable via the shared device + community detection.

## Ring 3 — smurfing hub (never reported)

- 7 small payments (Rs 4,000–9,000) from different base accounts into 3 collectors
  (`ACC_0472..ACC_0474`) over ~3.5 hours, collectors forward everything into **one
  hub `Manoj Gupta` (`ACC_0475`)**, which sends the lot to `COP_017` (Orbit Crypto
  Exchange). The 3 collectors share one phone. No fraud report; used to test **hub
  detection (PageRank)**.

## Decoy — the trap

- `ACC_0476` **Laxmi Kirana & General Store** (a legitimate busy merchant).
  Receives payments from **62 distinct senders** incl. a couple of large ones and a
  few at odd hours, so a naive "lots of inflow" rule flags it.
- Single stable device + phone; pays a supplier on a slow weekly schedule; 2 normal
  ATM withdrawals. **No fast onward forwarding** (never pays within 30 min of
  receiving). One payer is Ravi himself, so a lazy path search reaches it — but the
  agent must reject it because no path from Ravi's **stolen** money leads through it.
- Not labeled a decoy anywhere: `account_type = merchant`, no flag.

## Rebuilding

```bash
python scripts/generate_data.py   # base world
python scripts/plant_fraud.py     # plant rings + decoy + report (idempotent)
python scripts/validate_data.py   # base invariants (passes on merged data)
python scripts/validate_fraud.py  # fraud answer-key checks
```