# MuleTrace — 2-Minute Demo Script

Story: Victim **Ravi** loses **Rs 85,000** to a fake KYC call. The money leaves his
account at a known timestamp and moves through a chain — Ravi → Mule A → splits to
Mule B and Mule C → Mule D → Mule E → cash-out (ATM / crypto exchange) — all within
~12 minutes. Mule B shares a device with an account in a second, unreported ring; the
agent discovers that link. A **decoy** (busy local shop, many incoming payments) looks
suspicious but is legitimate and must NOT be frozen.

## Script

| Time | On screen | Agent does | I say |
| --- | --- | --- | --- |
| 0:00–0:10 | Title card, then the graph of ~500 nodes | — (idle) | "This is MuleTrace. Ravi just lost Rs 85,000 to a fake KYC call." |
| 0:10–0:20 | A fraud report dialog: victim=Ravi, amount=85000, time | Agent reads the report and starts tracing forward from Ravi | "We drop in the report — victim, amount, timestamp. The agent starts tracing the money." |
| 0:20–0:40 | Path lights up hop by hop: Ravi → A → B & C → D → E | `trace_money_forward` walks the chain across hops | "Watch the chain light up. Rs 85,000 → Mule A, splits into B and C, then D, then E — all within twelve minutes." |
| 0:40–0:55 | Shared-device edge flashes on Mule B | `find_shared_devices` connects Mule B to a second ring | "Mule B shares a phone with an account in a second ring that was never reported. Community detection surfaces it." |
| 0:55–1:10 | The decoy shop gets highlighted then grayed out | Agent evaluates the decoy, rejects freeze | "This shop looks busy — lots of incoming money. But no path from Ravi reaches it, so the agent leaves it alone and says why." |
| 1:10–1:25 | Freeze list renders, ranked | `build_freeze_list` ranks by money still held | "Here's the freeze list, ranked by what each account still holds: Ravi → A → B: Rs 40,000. Ravi → C → D → E: Rs 15,000." |
| 1:25–1:40 | Text explanation panel scrolls | Each item shows its full path + reason | "Every recommendation has its exact path, so an analyst always sees the evidence, not just a verdict." |
| 1:40–2:00 | Closing slide | — | "Real banks already hold the same payment-graph data. MuleTrace turns it into ranked, explainable freeze actions in seconds — catching rings before they cash out." |