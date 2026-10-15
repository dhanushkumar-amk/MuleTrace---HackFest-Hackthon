"""Phase 5: plant the fraud rings, decoy and fraud report on top of the base world.

Loads the pristine base world (from --base, or snapshots it from --out on the
first run), adds planted accounts in the reserved range ACC_0461..ACC_0500 via the
Phase 4 interface, and writes the merged final CSVs into --out. It is deterministic
(same --seed -> identical output) and idempotent: re-running starts again from the
pristine base snapshot and NEVER double-adds.

What gets planted (see docs/DATA_NOTES.md):
  Ring 1 (demo): Ravi (victim) -> A -> {B holds Rs 40,000} / C -> D -> E -> ATM.
                 Mules keep some money (commissions + terminal holders) so the
                 freeze list can be ranked by balance_held.
  Ring 2 (hidden): 5 mules on an earlier day, cash-out at a crypto exchange.
                 R2B shares ONE device with Ring 1's Mule B (the link the agent
                 must discover). No FraudReport.
  Ring 3 (smurfing): ~7 small payments from base accounts -> 3 collectors -> 1 hub
                 -> crypto exchange. Collectors share one phone. No FraudReport.
  Decoy: a legitimate busy merchant (>=60 distinct senders, one device + one phone,
                 slow weekly supplier payouts, no fast onward hops). One payer is
                 Ravi, so a lazy path search reaches it.
  Report: one FraudReport (Ravi). Ground truth -> tests/ground_truth.json.

No ring/mule/decoy label ever appears in a graph-bound CSV.

Usage:
    python scripts/generate_data.py                 # build the base world
    python scripts/plant_fraud.py --seed 7          # plant on top
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.world import load_world_from_dir, HEADERS  # noqa: E402
from datagen import REPO_ROOT  # noqa: E402

# ---------------------------------------------------------------------------
# Identities (deterministic, not rng-dependent)                          # (name, bank)
# ---------------------------------------------------------------------------
RING1 = [  # Ravi is separate; order: A,B,C,D,E -> ACC_0462..466
    ("A", "Suresh Reddy", "State Bank of India"),
    ("B", "Priya Iyer", "Axis Bank"),
    ("C", "Anil Nair", "ICICI Bank"),
    ("D", "Kavya Sharma", "Kotak Mahindra Bank"),
    ("E", "Rohit Mehta", "Bank of Baroda"),
]
RING2 = [  # R2A..R2E -> ACC_0467..471
    ("R2A", "Deepa Rao", "Union Bank of India"),
    ("R2B", "Arjun Pillai", "Canara Bank"),
    ("R2C", "Meena Kulkarni", "Yes Bank"),
    ("R2D", "Vikram Desai", "Punjab National Bank"),
    ("R2E", "Nisha Banerjee", "ICICI Bank"),
]
RING3 = [  # C1,C2,C3,H -> ACC_0472..475
    ("C1", "Farhan Khan", "HDFC Bank"),
    ("C2", "Geeta Joshi", "State Bank of India"),
    ("C3", "Prakash Shetty", "Axis Bank"),
    ("H", "Manoj Gupta", "ICICI Bank"),
]
DECOY = ("Laxmi Kirana & General Store", "Canara Bank")

# existing cash-out points (base world)
RING1_ATM = "COP_001"        # State Bank ATM - MG Road
RING2_EXCHANGE = "COP_016"   # Kaleido Exchange
RING3_EXCHANGE = "COP_017"   # Orbit Crypto Exchange
DECOY_ATM = "COP_003"

# Ring 1 scam amounts (conservation-guaranteed; demo: B=40k, E=15k)
R1_IN = 85_000
R1_AB = 40_000   # A -> B      (B holds all)
R1_AC = 45_000   # A -> C      (A keeps 0)
R1_CD = 44_000   # C -> D      (C keeps 1,000)
R1_DE = 43_000   # D -> E      (D keeps 1,000)
R1_CASH = 28_000  # E -> ATM    (E keeps 15,000)

FRAUD_REPORT_HEADER = ["id", "victim_account_id", "amount", "reported_at", "description"]


# ---------------------------------------------------------------------------
# {helpers}
# ---------------------------------------------------------------------------
def _fmt_phone(rng, used):
    while True:
        p = f"+91 9{rng.randint(0, 9999):04d} {rng.randint(0, 99999):05d}"
        if p not in used:
            used.add(p)
            return p


def _fmt_fp(rng, used):
    while True:
        fp = "DF-" + format(rng.getrandbits(56), "014x")
        if fp not in used:
            used.add(fp)
            return fp


def _pick(lst, rng):
    return lst[rng.randrange(len(lst))]


def _add_phone(world, rng, used):
    return world.add_phone(_fmt_phone(rng, used))


def _add_device(world, rng, used):
    return world.add_device(_fmt_fp(rng, used), rng.choice(["android"] * 3 + ["ios"]))


def _late_ts(rng, now):
    """A 'normal' timestamp well inside the 30-day window, before 'now'."""
    return (now - rng.randint(3, 25) * 86_400) - rng.randint(0, 8 * 3600)


def _innocent_spend(world, mule_id, base_merchants, rng, until_ts):
    """Two small purchases before until_ts; used to give mules a normal look."""
    for _ in range(2):
        amt = rng.choice([220, 350, 480, 640, 780, 900, 1150])
        ts = until_ts - rng.randint(2, 24) * 86_400 - rng.randint(0, 8 * 3600)
        world.add_transaction(mule_id, _pick(base_merchants, rng), amt, ts,
                              "UPI", "SUCCESS")
    return sum(p["amount"] for p in world.paid_edges
               if p["src"] == mule_id and p["dst"] in set(base_merchants))


# ---------------------------------------------------------------------------
# {ring planters}
# ---------------------------------------------------------------------------
def _plant_ring1(world, ids, ravi, rng, now, base_merchants, decoy_id):
    """Ravi (victim) + the demo chain. Returns Ravi's decoy-buy timestamp."""
    A, B, C, D, E = (ids["ring1"][t] for t in ("A", "B", "C", "D", "E"))

    # Ravi's normal pre-fraud life: a salary credit + ordinary purchases.
    salary_ts = (now - 12 * 86_400) + 9 * 3600
    world.add_transaction(_pick(base_merchants, rng), ravi, 50_000, salary_ts,
                          "IMPS", "SUCCESS")
    for i, amt in enumerate((2500, 1200, 900, 1800, 800, 700, 2400, 1200)):
        world.add_transaction(ravi, _pick(base_merchants, rng), amt,
                              now - (i + 3) * 86_400 - rng.randint(0, 8 * 3600),
                              "UPI", "SUCCESS")
    # Ravi also shops at the DECOY by coincidence (the lazy-path trap).
    ravi_decoy_ts = now - 11 * 86_400 - 7200
    world.add_transaction(ravi, decoy_id, 900, ravi_decoy_ts, "UPI", "SUCCESS")

    # The fraud chain (all within ~9.5 minutes; T0 = 2h before now).
    T0 = now - 7200
    world.add_transaction(ravi, A, R1_IN, T0, "UPI", "SUCCESS")
    world.add_transaction(A, B, R1_AB, T0 + 120, "IMPS", "SUCCESS")
    world.add_transaction(A, C, R1_AC, T0 + 150, "IMPS", "SUCCESS")
    world.add_transaction(C, D, R1_CD, T0 + 330, "IMPS", "SUCCESS")
    world.add_transaction(D, E, R1_DE, T0 + 450, "IMPS", "SUCCESS")
    world.add_transaction(E, None, R1_CASH, T0 + 570, "ATM", "SUCCESS",
                          cashout_point_id=RING1_ATM)

    # Mules look semi-normal: small innocent purchases before the fraud, funded
    # by their starting balance so the innocent activity nets to zero.
    starts = {ravi: 60_000}
    for mule in (A, B, C, D, E):
        spend = _innocent_spend(world, mule, base_merchants, rng, T0 - 2 * 3600)
        starts[mule] = spend
    return starts, ravi_decoy_ts


def _plant_ring2(world, ids, rng, now):
    """5 mules on an earlier day, cash-out at its own crypto exchange."""
    R = ids["ring2"]
    T0 = (now - 4 * 86_400) + 16 * 3600
    world.add_transaction(ids["ring2_funder"], R["R2A"], 60_000, T0, "NEFT", "SUCCESS")
    world.add_transaction(R["R2A"], R["R2B"], 30_000, T0 + 120, "IMPS", "SUCCESS")
    world.add_transaction(R["R2A"], R["R2C"], 28_000, T0 + 150, "IMPS", "SUCCESS")
    world.add_transaction(R["R2C"], R["R2D"], 27_000, T0 + 330, "IMPS", "SUCCESS")
    world.add_transaction(R["R2D"], R["R2E"], 26_000, T0 + 450, "IMPS", "SUCCESS")
    world.add_transaction(R["R2E"], None, 20_000, T0 + 570, "CRYPTO", "SUCCESS",
                          cashout_point_id=RING2_EXCHANGE)


def _plant_ring3(world, ids, rng, window_start):
    """Fan-in smurfing: 7 small payments -> 3 collectors -> 1 hub -> crypto."""
    C1, C2, C3, H = (ids["ring3"][t] for t in ("C1", "C2", "C3", "H"))
    start = window_start + 1 * 86_400 + 10 * 3600
    funders = rng.sample(ids["ring3_funders"], 7)
    buckets = [[], [], []]
    for i, f in enumerate(funders):
        buckets[i % 3].append((f, rng.randint(4000, 9000), start + i * 1800))
    for coll, funds in zip((C1, C2, C3), buckets):
        for f, amt, ts in funds:
            world.add_transaction(f, coll, amt, ts, "UPI", "SUCCESS")
        tot = sum(a for _, a, _ in funds)
        world.add_transaction(coll, H, tot, max(t for _, _, t in funds) + 900,
                              "IMPS", "SUCCESS")
    world.add_transaction(H, None,
                          sum(a for b in buckets for _, a, _ in b),
                          max(t for b in buckets for _, _, t in b) + 1800,
                          "CRYPTO", "SUCCESS", cashout_point_id=RING3_EXCHANGE)


def _plant_decoy(world, ids, rng, now, window_start, base_individuals, ravi):
    """A busy legitimate shop that looks suspicious to a naive inflow rule."""
    decoy = ids["decoy"]
    senders = rng.sample([i for i in base_individuals if i != ravi], 61) + [ravi]
    rng.shuffle(senders)

    base = window_start
    for k, s in enumerate(senders):
        if s == ravi:
            continue  # Ravi's decoy purchase was added in Ring 1
        if k == 0:
            amt, ts = 30_000, base + 20 * 86_400 + 10 * 3600
        elif k == 1:                       # big payments ~20 min apart -> >50k/hr
            amt, ts = 22_000, base + 20 * 86_400 + 10 * 3600 + 20 * 60
        elif k == 2:                       # a couple of odd-hour payments
            amt, ts = rng.choice([4200, 6800, 5500]), base + 2 * 86_400 + 3 * 3600
        elif k == 3:
            amt, ts = rng.choice([5100, 6300]), base + 8 * 86_400 + 2 * 3600
        else:
            amt = rng.randint(180, 3200)
            day = rng.randint(1, 30)
            hour = rng.choices(range(9, 23), weights=range(9, 23))[0]
            ts = base + (day - 1) * 86_400 + hour * 3600 + rng.randint(0, 59) * 60
        world.add_transaction(s, decoy, amt, ts, "UPI", "SUCCESS")
    # slow weekly supplier payouts (05:00) + 2 normal ATM withdrawals (06:00)
    supplier = ids["decoy_supplier"]
    for d in (3, 10, 17, 24):
        world.add_transaction(decoy, supplier, rng.choice([4200, 5000, 5800]),
                              base + (d - 1) * 86_400 + 5 * 3600, "NEFT", "SUCCESS")
    for d in (5, 19):
        world.add_transaction(decoy, None, rng.choice([8000, 9500, 11000]),
                              base + (d - 1) * 86_400 + 6 * 3600, "ATM", "SUCCESS",
                              cashout_point_id=DECOY_ATM)


# ---------------------------------------------------------------------------
def set_final_balances(world, planted_ids, starts):
    """balance_held = starting_balance + inflows - outflows (conservation)."""
    inflow, outflow = {}, {}
    for p in world.paid_edges:
        if p["src"] in planted_ids:
            outflow[p["src"]] = outflow.get(p["src"], 0) + p["amount"]
        if p["dst"] in planted_ids:
            inflow[p["dst"]] = inflow.get(p["dst"], 0) + p["amount"]
    for c in world.cashed_out_at:
        if c["account_id"] in planted_ids:
            outflow[c["account_id"]] = outflow.get(c["account_id"], 0) + c["amount"]
    for row in world.accounts:
        if row["id"] in planted_ids:
            row["balance_held"] = (starts.get(row["id"], 0)
                                   + inflow.get(row["id"], 0)
                                   - outflow.get(row["id"], 0))


def _snapshot_base(out_dir, base_dir):
    os.makedirs(base_dir, exist_ok=True)
    for name in list(HEADERS) + ["meta.json"]:
        shutil.copyfile(os.path.join(out_dir, name), os.path.join(base_dir, name))


def _is_pristine(out_dir):
    try:
        with open(os.path.join(out_dir, "accounts.csv")) as fh:
            return (sum(1 for _ in fh) - 1) <= 460
    except FileNotFoundError:
        return False


def _patch_usage(world, planted_ids):
    opened = {a["id"]: a["opened_at"] for a in world.accounts}
    for row in world.account_device:
        if row["account_id"] in planted_ids and int(row["first_seen"]) == 0:
            row["first_seen"] = opened[row["account_id"]]
            row["last_seen"] = 1792045800 - 3600  # a moment before 'now'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "data", "generated"))
    args = parser.parse_args()
    rng = random.Random(args.seed)

    out_dir = os.path.abspath(args.out)
    base_dir = os.path.join(out_dir, "base")

    if not os.path.isdir(base_dir) or not os.path.exists(os.path.join(base_dir, "accounts.csv")):
        if not _is_pristine(out_dir):
            print("[error] no pristine base: run scripts/generate_data.py first "
                  f"(or clear {base_dir})", file=sys.stderr)
            return 1
        _snapshot_base(out_dir, base_dir)
        print(f"[base] snapshotted pristine base -> {base_dir}")

    world = load_world_from_dir(base_dir)
    window_start = world.meta["window_start"]
    now = world.meta["window_end"]
    base_merchants = [a["id"] for a in world.accounts if a["account_type"] == "merchant"]
    base_individuals = [a["id"] for a in world.accounts if a["account_type"] == "individual"]
    used_phones = {p["number"] for p in world.phones}
    used_fps = {d["device_fingerprint"] for d in world.devices}

    # ---- create accounts (reserved ACC_0461..) ---------------------------
    ravi = world.add_account("Ravi Kumar", "HDFC Bank", "individual",
                             now - 2 * 365 * 86_400, 0, False, 0)
    ids = {"ring1": {}, "ring2": {}, "ring3": {}}
    for tag, name, bank in RING1:
        ids["ring1"][tag] = world.add_account(name, bank, "individual",
                                              now - rng.randint(720, 1200) * 86_400,
                                              0, False, 0)
    for tag, name, bank in RING2:
        ids["ring2"][tag] = world.add_account(name, bank, "individual",
                                              now - rng.randint(600, 1100) * 86_400,
                                              0, False, 0)
    for tag, name, bank in RING3:
        ids["ring3"][tag] = world.add_account(name, bank, "individual",
                                              now - rng.randint(500, 1000) * 86_400,
                                              0, False, 0)
    decoy_name, decoy_bank = DECOY
    decoy = world.add_account(decoy_name, decoy_bank, "merchant",
                              now - 3 * 365 * 86_400, 0, False, 0)
    ids["decoy"] = decoy
    ids["ring2_funder"] = _pick(base_individuals, rng)
    ids["decoy_supplier"] = _pick(base_merchants, rng)
    ids["ring3_funders"] = base_individuals  # sampled at plant time
    planted_ids = [ravi] + [c for r in (ids["ring1"], ids["ring2"], ids["ring3"])
                            for c in r.values()] + [decoy]

    # ---- phones ----------------------------------------------------------
    for aid in planted_ids:
        world.add_phone_link(aid, _add_phone(world, rng, used_phones))
    # ring 3 collectors share one phone
    shared_phone = _add_phone(world, rng, used_phones)
    for c in ("C1", "C2", "C3"):
        cid = ids["ring3"][c]
        old = next(r["phone_id"] for r in world.account_phone
                   if r["account_id"] == cid)
        world.account_phone = [r for r in world.account_phone
                               if not (r["account_id"] == cid)]
        world.phones = [p for p in world.phones if p["id"] != old]  # drop unused
        world.account_phone.append({"account_id": cid, "phone_id": shared_phone})

    # ---- devices ---------------------------------------------------------
    own = dict(ids["ring1"]) | dict(ids["ring2"]) | dict(ids["ring3"])
    own["ravi"] = ravi
    own["decoy"] = decoy
    for aid in own.values():
        d = _add_device(world, rng, used_fps)
        world.add_device_link(aid, d, 0, 0)
    # the shared device between Ring 1's Mule B and Ring 2's R2B
    shared_dev = _add_device(world, rng, used_fps)
    world.add_device_link(ids["ring1"]["B"], shared_dev, 0, 0)
    world.add_device_link(ids["ring2"]["R2B"], shared_dev, 0, 0)

    # ---- plant the rings --------------------------------------------------
    starts, ravi_decoy_ts = _plant_ring1(world, ids, ravi, rng, now,
                                         base_merchants, decoy)
    _plant_ring2(world, ids, rng, now)
    _plant_ring3(world, ids, rng, window_start)
    _plant_decoy(world, ids, rng, now, window_start, base_individuals, ravi)

    starts[decoy] = 40_000
    for aid in planted_ids:
        starts.setdefault(aid, 0)
    set_final_balances(world, planted_ids, starts)
    _patch_usage(world, planted_ids)

    world.write_all(out_dir)
    _write_report_and_ground_truth(world, ids, ravi, now, starts, out_dir)

    print(f"== planted fraud rings + decoy (seed={args.seed}) -> {out_dir}")
    print(f"   accounts: {len(world.accounts)}  transactions: {len(world.transactions)}")
    print(f"   Ravi={ravi}  freeze list:")
    gt = json.load(open(os.path.join(REPO_ROOT, "tests", "ground_truth.json")))
    for it in gt["expected_freeze_list"]:
        print(f"     {it['account']}  Rs {it['balance_held']:,}  "
              f"{' -> '.join(it['path'])}")
    return 0


def _ring1_freeze(world, ids, ravi):
    A = ids["ring1"]
    paths = {
        A["B"]: [ravi, A["A"], A["B"]],
        A["C"]: [ravi, A["A"], A["C"]],
        A["D"]: [ravi, A["A"], A["C"], A["D"]],
        A["E"]: [ravi, A["A"], A["C"], A["D"], A["E"]],
    }
    bal = {a["id"]: a["balance_held"] for a in world.accounts}
    items = [{"account": m, "balance_held": bal[m], "path": paths[m]} for m in paths]
    items.sort(key=lambda it: (-it["balance_held"], it["account"]))
    return items


def _write_report_and_ground_truth(world, ids, ravi, now, starts, out_dir):
    reported_at = (now - 7200) + 6300
    report = {"id": "FR_0001", "victim_account_id": ravi, "amount": 85_000,
              "reported_at": int(reported_at),
              "description": ("Victim got a 'KYC verification' call and followed "
                              "the scammer's steps; Rs 85,000 left the account via "
                              "UPI to an unknown account.")}
    with open(os.path.join(out_dir, "fraud_reports.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FRAUD_REPORT_HEADER)
        w.writeheader()
        w.writerow(report)

    bal = {a["id"]: a["balance_held"] for a in world.accounts}
    gt = {
        "seed": 7,
        "report_id": "FR_0001",
        "victim_account_id": ravi,
        "report_amount": 85_000,
        "reported_at": int(reported_at),
        "rings": {
            "1": {"accounts": [ids["ring1"][t] for t in "ABCDE"],
                  "chain_forward": [ravi, ids["ring1"]["A"], ids["ring1"]["B"]],
                  "chain_cashout": [ravi, ids["ring1"]["A"], ids["ring1"]["C"],
                                    ids["ring1"]["D"], ids["ring1"]["E"]],
                  "cashout_point": RING1_ATM, "cashout_account": ids["ring1"]["E"]},
            "2": {"accounts": [ids["ring2"][t] for t in
                               ("R2A", "R2B", "R2C", "R2D", "R2E")],
                  "chain_forward": [ids["ring2"]["R2A"], ids["ring2"]["R2B"]],
                  "chain_cashout": [ids["ring2"]["R2A"], ids["ring2"]["R2C"],
                                    ids["ring2"]["R2D"], ids["ring2"]["R2E"]],
                  "cashout_point": RING2_EXCHANGE,
                  "cashout_account": ids["ring2"]["R2E"]},
            "3": {"accounts": [ids["ring3"][t] for t in ("C1", "C2", "C3", "H")],
                  "collectors": [ids["ring3"][t] for t in ("C1", "C2", "C3")],
                  "hub": ids["ring3"]["H"],
                  "cashout_point": RING3_EXCHANGE,
                  "cashout_account": ids["ring3"]["H"]},
        },
        "shared_device_link": {"device_id": _find_shared(world, ids["ring1"]["B"],
                                                         ids["ring2"]["R2B"]),
                               "ring1_account": ids["ring1"]["B"],
                               "ring2_account": ids["ring2"]["R2B"]},
        "decoy_account_id": ids["decoy"],
        "ring3_hub": ids["ring3"]["H"],
        "expected_freeze_list": _ring1_freeze(world, ids, ravi),
        "starting_balances": starts,
        "final_balances": bal,
        "reserved_range": {"first": "ACC_0461", "last": "ACC_0500"},
    }
    os.makedirs(os.path.join(REPO_ROOT, "tests"), exist_ok=True)
    with open(os.path.join(REPO_ROOT, "tests", "ground_truth.json"), "w",
              encoding="utf-8") as fh:
        json.dump(gt, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _find_shared(world, b_id, other_id):
    """The device used by BOTH b_id and other_id (the planted shared device)."""
    used = {}
    for r in world.account_device:
        used.setdefault(r["account_id"], set()).add(r["device_id"])
    return sorted(used.get(b_id, set()) & used.get(other_id, set()))[0]


if __name__ == "__main__":
    sys.exit(main())