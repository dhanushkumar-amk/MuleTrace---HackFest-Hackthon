"""Validate the generated MuleTrace base data in data/generated/.

Prints PASS/FAIL for every check and a summary; exits non-zero if any check fails.

Checks:
  1. row counts within expected ranges
  2. no duplicate ids / phone numbers, no dangling references
  3. all transaction/paid/cash-out timestamps inside the 30-day window, amounts > 0
  4. every inter-account transaction has a matching PAID row (and vice-versa)
  5. sender never equals receiver
  6. at least 30 accounts share a device, and at least 5 rapid-forward patterns
  7. amount distribution looks reasonable (prints median, p95, max)
  8. reproducibility: generating twice with the same seed gives identical files

Usage:
    python scripts/validate_data.py
    python scripts/validate_data.py --dir data/generated
"""
from __future__ import annotations

import argparse
import hashlib
import os
import statistics
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.world import load_world_from_dir, FILES  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATE_SCRIPT = os.path.join(REPO_ROOT, "scripts", "generate_data.py")
PASSED = True

MOVED_COLS = ("amount", "timestamp")


def report(step: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if not ok:
        PASSED = False
    print(f"[{'PASS' if ok else 'FAIL'}] {step}" + (f" - {detail}" if detail else ""))


def in_range(got, lo, hi):
    return lo <= got <= hi, f"got={got} expected~[{lo}, {hi}]"


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------
def check_structure(world) -> None:
    accounts = {a["id"] for a in world.accounts}
    devices = {d["id"] for d in world.devices}
    phones = {p["id"] for p in world.phones}
    txns = {t["id"] for t in world.transactions}
    cashouts = {c["id"] for c in world.cashout_points}
    phone_nums = {p["number"] for p in world.phones}

    # duplicate ids
    report("no duplicate account ids", len(accounts) == len(world.accounts))
    report("no duplicate device ids", len(devices) == len(world.devices))
    report("no duplicate phone ids", len(phones) == len(world.phones))
    report("no duplicate phone numbers", len(phone_nums) == len(world.phones))
    report("no duplicate transaction ids", len(txns) == len(world.transactions))
    report("no duplicate cash-out-point ids", len(cashouts) == len(world.cashout_points))

    # dangling references
    bad_txn = [t for t in world.transactions
               if t["sender_account_id"] not in accounts
               or (t["receiver_account_id"] and t["receiver_account_id"] not in accounts)]
    report("every transaction references an existing account",
           not bad_txn, f"bad={bad_txn[:3]}")
    bad_ud = [r for r in world.account_device
              if r["account_id"] not in accounts or r["device_id"] not in devices]
    report("every device usage references account + device",
           not bad_ud, f"bad={bad_ud[:3]}")
    bad_up = [r for r in world.account_phone
              if r["account_id"] not in accounts or r["phone_id"] not in phones]
    report("every phone registration references account + phone",
           not bad_up, f"bad={bad_up[:3]}")
    bad_paid = [p for p in world.paid_edges
                if p["src"] not in accounts or p["dst"] not in accounts]
    report("every PAID edge references two accounts", not bad_paid, f"bad={bad_paid[:3]}")
    bad_co = [c for c in world.cashed_out_at
              if c["account_id"] not in accounts or c["cashout_point_id"] not in cashouts]
    report("every cash-out row references account + cash-out point",
           not bad_co, f"bad={bad_co[:3]}")


def check_time_and_amount(world, meta) -> None:
    lo, hi = meta["window_start"], meta["window_end"]
    for name in ("transactions", "paid_edges", "cashed_out_at"):
        rows = getattr(world, name)
        oob = [r for r in rows if not (lo <= r["timestamp"] <= hi)]
        nonpos = [r for r in rows if r["amount"] <= 0]
        report(f"{name} timestamps inside window", not oob, f"oob={oob[:3]}")
        report(f"{name} amounts positive", not nonpos, f"nonpos={nonpos[:3]}")


def check_paid_consistency(world) -> None:
    with_receiver = {t["id"]: t for t in world.transactions if t["receiver_account_id"]}
    report("PAID rows cover exactly the inter-account transactions",
           len(world.paid_edges) == len(with_receiver),
           f"paid={len(world.paid_edges)} inter_txns={len(with_receiver)}")
    by_txn = {}
    for p in world.paid_edges:
        by_txn.setdefault(p["txn_id"], []).append(p)
    mismatched = []
    for txn_id, txn in with_receiver.items():
        edges = by_txn.get(txn_id, [])
        if len(edges) != 1:
            mismatched.append((txn_id, "count"))
            continue
        e = edges[0]
        if (e["src"], e["dst"], e["amount"], e["timestamp"]) != \
           (txn["sender_account_id"], txn["receiver_account_id"],
            txn["amount"], txn["timestamp"]):
            mismatched.append((txn_id, "mismatch"))
    orphan = [p["txn_id"] for p in world.paid_edges if p["txn_id"] not in with_receiver]
    report("every inter-account transaction has a matching PAID row (amount/ts/src/dst)",
           not mismatched, f"bad={mismatched[:3]}")
    report("no orphan PAID rows", not orphan, f"orphan={orphan[:3]}")


def check_sender_receiver(world) -> None:
    bad = [t for t in world.transactions
           if t["receiver_account_id"] and t["sender_account_id"] == t["receiver_account_id"]]
    report("sender never equals receiver (transactions)", not bad, f"bad={bad[:3]}")

    # also confirm cash-outs have no receiver (they exit the system)
    atm = [t for t in world.transactions if t["channel"] == "ATM"]
    atm_no_recv = [t for t in atm if not t["receiver_account_id"]]
    report(f"ATM withdrawals have no receiver (cash-out), {len(atm)} total",
           len(atm_no_recv) == len(atm), f"atm={len(atm)}")


def check_noise(world) -> None:
    from datagen.devices import shared_device_stats
    n_shared, n_involved = shared_device_stats(world)
    report("device sharing is present (>=30 accounts share a device)",
           n_involved >= 30, f"shared_devices={n_shared}, accounts={n_involved}")

    # rapid forward patterns: A->B then B->C within 10 minutes, amount doesn't grow
    incoming = {}
    outgoing = {}
    for p in world.paid_edges:
        incoming.setdefault(p["dst"], []).append(p)
        outgoing.setdefault(p["src"], []).append(p)
    patterns = 0
    for b, ins in incoming.items():
        for inc in ins:
            for out in outgoing.get(b, []):
                dt = out["timestamp"] - inc["timestamp"]
                if 0 < dt <= 600 and out["amount"] <= inc["amount"]:
                    patterns += 1
    report(f"legitimate rapid multi-hop patterns exist (>=5, found {patterns})",
           patterns >= 5)


def check_distribution(world, meta) -> None:
    amounts = [t["amount"] for t in world.transactions]
    amounts.sort()
    median = statistics.median(amounts)
    p95 = amounts[int(round(0.95 * (len(amounts) - 1)))]
    print(f"[INFO] amount distribution: median={median} p95={p95} max={max(amounts)}")


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
def check_reproducible(meta) -> None:
    seed = meta["seed"]
    scale = meta["scale"]
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, GENERATE_SCRIPT, "--seed", str(seed),
               "--scale", str(scale), "--out", tmp]
        subprocess.run(cmd, check=True, capture_output=True, cwd=REPO_ROOT)
        for fname in FILES + ["meta.json"]:
            a = os.path.join(REPO_ROOT, "data", "generated", fname)
            b = os.path.join(tmp, fname)
            if not _same_hash(a, b):
                report(f"reproducible: {fname}", False, "hashes differ")
                return
    report("reproducible (same seed -> identical files)", True)


def _same_hash(p1, p2) -> bool:
    def h(p):
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    return h(p1) == h(p2)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(world, meta) -> None:
    from datagen.devices import shared_device_stats
    n_shared, n_involved = shared_device_stats(world)
    merchants = {a["id"] for a in world.accounts if a["account_type"] == "merchant"}
    inc_count = {}
    for p in world.paid_edges:
        if p["dst"] in merchants:
            inc_count[p["dst"]] = inc_count.get(p["dst"], 0) + 1
    busiest = max(inc_count, key=inc_count.get) if inc_count else None
    busiest_name = busiest and next(a["holder_name"] for a in world.accounts
                                    if a["id"] == busiest)
    print("== summary ==")
    for name in FILES:
        attr = name[:-4]
        print(f"   {attr:>18}: {len(getattr(world, attr))}")
    print(f"   shared-device groups: {n_shared} ({n_involved} accounts involved)")
    print(f"   busiest merchant: {busiest} ({busiest_name}, {inc_count.get(busiest, 0)} txns)")
    print(f"   window: {meta['window_start_iso']} .. {meta['window_end_iso']}")


# ---------------------------------------------------------------------------
def check_counts(world, meta) -> None:
    scale = meta["scale"]
    budget = round(5000 * scale)
    n_atm = meta["n_atm"]
    expected = {
        "accounts": (meta["base_accounts"] - 5, meta["base_accounts"] + 5),
        "phones": (445, 470),
        "account_phone": (meta["n_accounts"] - 5, meta["n_accounts"] + 5),
        "devices": (548, 610),
        "account_device": (580, 660),
        "cashout_points": (20, 20),
        "transactions": (int(budget * 0.95), int(budget * 1.05)),
        "paid_edges": (int(budget * 0.95) - n_atm - 10, int(budget * 1.05) - n_atm + 10),
        "cashed_out_at": (n_atm - 10, n_atm + 10),
    }
    for name in FILES:
        stem = name[:-4]
        got = len(getattr(world, stem))
        lo, hi = expected[stem]
        ok, detail = in_range(got, lo, hi)
        report(f"row count {name}", ok, detail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=os.path.join(REPO_ROOT, "data", "generated"),
                        help="generated data directory")
    args = parser.parse_args()

    world = load_world_from_dir(args.dir)
    meta = world.meta
    print(f"== validating {args.dir} (seed={meta['seed']}, scale={meta['scale']}) ==")

    check_counts(world, meta)
    check_structure(world)
    check_time_and_amount(world, meta)
    check_paid_consistency(world)
    check_sender_receiver(world)
    check_noise(world)
    check_distribution(world, meta)
    print_summary(world, meta)
    check_reproducible(meta)

    print("=" * 40)
    if PASSED:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())