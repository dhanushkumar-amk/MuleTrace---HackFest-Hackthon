"""Validate the Phase 5 planted fraud data against tests/ground_truth.json.

Prints PASS/FAIL for every check and a summary; exits non-zero if any check fails.

Checks (see docs/DATA_NOTES.md + docs/ACCEPTANCE.md):
  A. planted ids all in the reserved range, no duplicates / dangling refs
  B. Ring 1 chain: spans 8-14 min, money only moves forward in time
  C. money conservation: balance_held == starting + inflows - outflows per mule
  D. Ring 1 expected freeze list matches the actual balances
  E. Ring 2 shares exactly one device with Ring 1's Mule B; no FraudReport
  F. decoy: >=60 distinct senders, one device, one phone, no fast onward hop
  G. Ring 3: fan-in count, single hub, hub reaches a crypto exchange
  H. no ring_id / mule / decoy flag in any graph-bound CSV
  I. naive baseline ("inflow > Rs 50,000 in 1 hour") flags the decoy
  J. base noise preserved: scripts/validate_data.py passes on the merged data
  K. determinism: regenerating with the same seed gives identical file hashes

Usage:
    python scripts/validate_fraud.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.world import load_world_from_dir, HEADERS  # noqa: E402
from datagen import REPO_ROOT  # noqa: E402

PASSED = True

GENERATE_SCRIPT = os.path.join(REPO_ROOT, "scripts", "generate_data.py")
PLANT_SCRIPT = os.path.join(REPO_ROOT, "scripts", "plant_fraud.py")
VALIDATE_SCRIPT = os.path.join(REPO_ROOT, "scripts", "validate_data.py")
GT_PATH = os.path.join(REPO_ROOT, "tests", "ground_truth.json")

FORBIDDEN = ("ring_id", "is_planted", "mule", "decoy")


def report(step: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if not ok:
        PASSED = False
    print(f"[{'PASS' if ok else 'FAIL'}] {step}" + (f" - {detail}" if detail else ""))


def planted_accounts(gt):
    accs = [gt["victim_account_id"]]
    accs += gt["rings"]["1"]["accounts"] + gt["rings"]["2"]["accounts"]
    accs += gt["rings"]["3"]["accounts"]
    accs.append(gt["decoy_account_id"])
    return accs


def _num(account_id: str) -> int:
    return int(account_id.split("_")[1])


# ---------------------------------------------------------------------------
# A. reserved range / dupes / refs
# ---------------------------------------------------------------------------
def check_reserved(world, gt) -> None:
    lo = _num(gt["reserved_range"]["first"])
    hi = _num(gt["reserved_range"]["last"])
    ids = planted_accounts(gt)
    report("planted ids all in reserved range",
           all(lo <= _num(i) <= hi for i in ids),
           f"range=ACC_{lo:04d}..ACC_{hi:04d}")
    report("no duplicate planted ids", len(set(ids)) == len(ids))
    holders = {a["id"] for a in world.accounts}
    missing = [i for i in ids if i not in holders]
    report("every planted account exists in accounts.csv", not missing, f"missing={missing}")
    # account_type stays individual/merchant (a planted mule must be discoverable)
    types = {a["id"]: a["account_type"] for a in world.accounts}
    bad = {i: types[i] for i in ids if types.get(i) not in ("individual", "merchant")}
    report("planted account_type is only individual/merchant (no mule label)",
           not bad, f"bad={bad}")


# ---------------------------------------------------------------------------
# B. Ring 1 chain times
# ---------------------------------------------------------------------------
def check_ring1_chain(world, gt) -> None:
    r1 = gt["rings"]["1"]
    pairs = set()
    for chain in (r1["chain_forward"], r1["chain_cashout"]):
        for a, b in zip(chain, chain[1:]):
            pairs.add((a, b))
    ts_by_pair = {}
    for p in world.paid_edges:
        if (p["src"], p["dst"]) in pairs:
            ts_by_pair[(p["src"], p["dst"])] = p["timestamp"]
    cash_ts = [c["timestamp"] for c in world.cashed_out_at
               if c["account_id"] == r1["cashout_account"]]
    times = sorted(list(ts_by_pair.values()) + cash_ts)
    span = times[-1] - times[0]
    report(f"Ring 1 chain spans 8-14 minutes (span={span}s, {span/60:.1f}min)",
           480 <= span <= 840)
    increasing = all(b > a for a, b in zip(times, times[1:]))
    report("Ring 1 money only moves forward in time", increasing,
           f"events={times}")


# ---------------------------------------------------------------------------
# C. conservation   D. freeze list
# ---------------------------------------------------------------------------
def account_flows(world):
    inflow, outflow = {}, {}
    for p in world.paid_edges:
        outflow[p["src"]] = outflow.get(p["src"], 0) + p["amount"]
        inflow[p["dst"]] = inflow.get(p["dst"], 0) + p["amount"]
    for c in world.cashed_out_at:
        outflow[c["account_id"]] = outflow.get(c["account_id"], 0) + c["amount"]
    return inflow, outflow


def check_conservation(world, gt) -> None:
    inflow, outflow = account_flows(world)
    bal = {a["id"]: a["balance_held"] for a in world.accounts}
    starts = gt["starting_balances"]
    bad = []
    for acct in planted_accounts(gt):
        expected = starts.get(acct, 0) + inflow.get(acct, 0) - outflow.get(acct, 0)
        if bal.get(acct) != expected:
            bad.append((acct, bal.get(acct), expected))
    report("money conservation: balance_held == starting + in - out for every planted mule",
           not bad, f"bad={bad[:5]}")


def check_freeze_list(world, gt) -> None:
    bal = {a["id"]: a["balance_held"] for a in world.accounts}
    expected = gt["expected_freeze_list"]
    mismatch = [it["account"] for it in expected if bal.get(it["account"]) != it["balance_held"]]
    report("freeze-list balances match accounts.csv", not mismatch, f"mismatch={mismatch}")
    sort = [it["balance_held"] for it in expected]
    ok_order = all(sort[i] >= sort[i + 1] for i in range(len(sort) - 1))
    report("freeze list is ordered by balance_held desc", ok_order)
    # every entry is >=2 hops from Ravi (path length >= 3 incl victim)
    ok_hops = all(len(it["path"]) >= 3 for it in expected)
    report("each freeze entry has a path of >=2 hops from Ravi", ok_hops)


# ---------------------------------------------------------------------------
# E. Ring 2 shared device / no report
# ---------------------------------------------------------------------------
def check_ring2(world, gt) -> None:
    r1_b = gt["rings"]["1"]["chain_forward"][-1]
    ring2 = set(gt["rings"]["2"]["accounts"])
    used = {}
    for r in world.account_device:
        used.setdefault(r["account_id"], set()).add(r["device_id"])
    shared = used[r1_b] & set().union(*[used[a] for a in ring2]) if ring2 else set()
    link = gt["shared_device_link"]
    report(f"Ring 1 Mule B shares exactly one device with Ring 2 (found {len(shared)})",
           len(shared) == 1, f"device={shared}")
    report("shared device matches ground truth",
           shared == {link["device_id"]}
           and link["ring2_account"] in ring2
           and link["ring1_account"] == r1_b)
    # no fraud report for ring 2 (and none for ring 3)
    victims = _report_victims(world)
    overlap = victims & ring2
    report("Ring 2 has no FraudReport", not overlap, f"victims={victims}")


# ---------------------------------------------------------------------------
# F. Decoy
# ---------------------------------------------------------------------------
def check_decoy(world, gt) -> None:
    decoy = gt["decoy_account_id"]
    senders = {p["src"] for p in world.paid_edges if p["dst"] == decoy}
    report(f"decoy has >=60 distinct senders (got {len(senders)})", len(senders) >= 60)
    n_dev = len({r["device_id"] for r in world.account_device if r["account_id"] == decoy})
    n_ph = len({r["phone_id"] for r in world.account_phone if r["account_id"] == decoy})
    report("decoy has one stable device", n_dev == 1, f"devices={n_dev}")
    report("decoy has one phone", n_ph == 1, f"phones={n_ph}")
    # no outgoing within 30 min of an incoming
    inc = sorted(p["timestamp"] for p in world.paid_edges if p["dst"] == decoy)
    out = ([p["timestamp"] for p in world.paid_edges if p["src"] == decoy]
           + [c["timestamp"] for c in world.cashed_out_at if c["account_id"] == decoy])
    fast = [t for t in out if any(t - 1800 <= i < t for i in inc)]
    report("decoy has no outgoing within 30 min of an incoming", not fast, f"fast={fast[:5]}")


# ---------------------------------------------------------------------------
# G. Ring 3
# ---------------------------------------------------------------------------
def check_ring3(world, gt) -> None:
    r3 = gt["rings"]["3"]
    collectors = set(r3["collectors"])
    hub = r3["hub"]
    funders = {p["src"] for p in world.paid_edges if p["dst"] in collectors}
    report(f"Ring 3 fan-in from >=6 distinct funders (got {len(funders)})",
           len(funders) >= 6)
    collector_out = {p["dst"] for p in world.paid_edges if p["src"] in collectors}
    report(f"Ring 3 collectors forward to a single hub ({collector_out})",
           collector_out == {hub})
    kinds = {c["id"]: c["kind"] for c in world.cashout_points}
    hub_cash = [c for c in world.cashed_out_at if c["account_id"] == hub]
    crypto = [c for c in hub_cash if kinds.get(c["cashout_point_id"]) == "CRYPTO_EXCHANGE"]
    report("Ring 3 hub reaches a crypto exchange", bool(crypto), f"cash={hub_cash}")


# ---------------------------------------------------------------------------
# H. no flags in graph CSV
# ---------------------------------------------------------------------------
def check_no_flag(world, dir_path) -> None:
    offenders = []
    for name in HEADERS:
        with open(os.path.join(dir_path, name), encoding="utf-8") as fh:
            text = fh.read().lower()
        found = [t for t in FORBIDDEN if t.lower() in text]
        if found:
            offenders.append((name, found))
    report("no ring_id / mule / decoy flag in any graph-bound CSV",
           not offenders, f"found={offenders}")
    types = {a["account_type"] for a in world.accounts}
    report("account_type values stay in {individual, merchant}",
           types <= {"individual", "merchant"}, f"types={types}")


# ---------------------------------------------------------------------------
# I. naive baseline
# ---------------------------------------------------------------------------
def naive_baseline(world, gt) -> None:
    incoming = {}
    for p in world.paid_edges:
        incoming.setdefault(p["dst"], []).append((p["timestamp"], p["amount"]))
    flagged = {}
    for acct, ev in incoming.items():
        ev.sort()
        best = 0
        for i, (ts, _) in enumerate(ev):
            s = 0
            j = i
            while j < len(ev) and ev[j][0] <= ts + 3600:
                s += ev[j][1]
                j += 1
            best = max(best, s)
        if best > 50_000:
            flagged[acct] = best
    decoy = gt["decoy_account_id"]
    print(f"[INFO] naive baseline (inflow > Rs 50,000 in 1 hour) flags "
          f"{len(flagged)} accounts, incl. decoy={decoy in flagged}")
    report("naive baseline flags the decoy", decoy in flagged)


# ---------------------------------------------------------------------------
# J. base noise preserved (validate_data passes)
# ---------------------------------------------------------------------------
def check_base_noise(dir_path) -> None:
    r = subprocess.run([sys.executable, VALIDATE_SCRIPT, "--dir", dir_path],
                       capture_output=True, text=True, cwd=REPO_ROOT)
    ok = "ALL CHECKS PASSED" in r.stdout and r.returncode == 0
    tail = r.stdout.strip().splitlines()[-1] if r.stdout else ""
    report("base noise preserved (validate_data.py passes on merged data)", ok, tail)


# ---------------------------------------------------------------------------
# K. determinism
# ---------------------------------------------------------------------------
def check_determinism(dir_path, meta) -> None:
    seed = meta["seed"]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, GENERATE_SCRIPT, "--seed", str(seed),
                        "--out", tmp], check=True, capture_output=True, cwd=REPO_ROOT)
        subprocess.run([sys.executable, PLANT_SCRIPT, "--seed", str(seed),
                        "--out", tmp], check=True, capture_output=True, cwd=REPO_ROOT)
        for fname in list(HEADERS) + ["meta.json", "fraud_reports.csv"]:
            if not _same(os.path.join(dir_path, fname), os.path.join(tmp, fname)):
                report(f"determinism: {fname}", False, "hashes differ")
                return
    report("deterministic (same seed -> identical file hashes)", True)


def _same(p1, p2) -> bool:
    def h(p):
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    return h(p1) == h(p2)


def _report_victims(world) -> set:
    try:
        import csv
        path = os.path.join(REPO_ROOT, "data", "generated", "fraud_reports.csv")
        with open(path) as fh:
            return {r["victim_account_id"] for r in csv.DictReader(fh)}
    except FileNotFoundError:
        return set()


def print_summary(world, gt) -> None:
    print("== summary ==")
    for ring, key in (("1", "accounts"), ("2", "accounts"), ("3", "accounts")):
        print(f"   Ring {ring}: {', '.join(gt['rings'][ring][key])}")
    print(f"   decoy: {gt['decoy_account_id']}   ring3 hub: {gt['ring3_hub']}")
    print(f"   shared device: {gt['shared_device_link']['device_id']} "
          f"(Ring1 {gt['shared_device_link']['ring1_account']} <-> Ring2 "
          f"{gt['shared_device_link']['ring2_account']})")
    print(f"   fraud report: {gt['report_id']} victim={gt['victim_account_id']}")
    print("   expected freeze list:")
    for it in gt["expected_freeze_list"]:
        print(f"      {it['account']}  Rs {it['balance_held']:,}  "
              f"{' -> '.join(it['path'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=os.path.join(REPO_ROOT, "data", "generated"))
    args = parser.parse_args()

    world = load_world_from_dir(args.dir)
    with open(GT_PATH, encoding="utf-8") as fh:
        gt = json.load(fh)
    print(f"== validating Phase 5 fraud (seed={gt.get('seed')}) ==")

    check_reserved(world, gt)
    check_ring1_chain(world, gt)
    check_conservation(world, gt)
    check_freeze_list(world, gt)
    check_ring2(world, gt)
    check_decoy(world, gt)
    check_ring3(world, gt)
    check_no_flag(world, args.dir)
    naive_baseline(world, gt)
    check_base_noise(args.dir)
    check_determinism(args.dir, world.meta)
    print_summary(world, gt)

    print("=" * 40)
    if PASSED:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())