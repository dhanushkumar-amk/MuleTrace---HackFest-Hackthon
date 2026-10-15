"""In-memory world model for MuleTrace synthetic data, plus the Phase 5 API.

This holds the base (normal, non-fraud) world built by `generate_data.py`. It is
deliberately the seam Phase 5 uses to ADD planted mule/decoy accounts and money
chains ON TOP of the base world without regenerating it.

Public interface (what Phase 5 should call)
-------------------------------------------
    world = datagen.build_base_world(seed, scale)      # fresh normal world
    # -- OR, to extend an already-written dataset without rebuilding:
    world = datagen.load_world_from_dir("data/generated")

    # add a planted account (auto-assigns the next free ACC/P H/DEV id):
    mule = world.add_account(
        holder_name="Mule A", bank="HDFC Bank", account_type="mule_suspect",
        opened_at=..., balance_held=0, is_flagged=False, risk_score=0,
    )
    # chain money through the graph (auto-assigns TXN ids, keeps PAID +
    # SENT/RECEIVED_BY projections in sync):
    world.add_transaction(sender="Ravi", receiver=mule, amount=40000,
                          timestamp=..., channel="UPI", status="SUCCESS")
    world.add_transaction(sender=mule, receiver="Mule B", amount=15000,
                          timestamp=..., channel="IMPS", status="SUCCESS")
    # give a mule a device/phone if the story needs a shared-device link:
    world.add_device_link(account_id=mule, device_id="DEV_0001",
                          first_seen=..., last_seen=...)
    world.add_phone_link(account_id="Ravi", phone_id="PH_0001")

    world.write_all("data/generated")   # rewrite every CSV atomically

All IDs continue automatically from where the base world left off, so Phase 5
never needs to know them. Account IDs ACC_0461..ACC_0500 are RESERVED for Phase 5
(40 slots for mules + the decoy merchant); phones/devices/transactions continue
from the highest existing sequence number.
"""
from __future__ import annotations

import csv
import os

# ---------------------------------------------------------------------------
# File / column layout (every CSV is plain text; docs/SCHEMA.md column names)
# ---------------------------------------------------------------------------
FILES = [
    "accounts.csv",
    "phones.csv",
    "account_phone.csv",
    "devices.csv",
    "account_device.csv",
    "cashout_points.csv",
    "transactions.csv",
    "paid_edges.csv",
    "cashed_out_at.csv",
]

HEADERS = {
    "accounts.csv": ["id", "holder_name", "bank", "account_type", "opened_at",
                     "balance_held", "is_flagged", "risk_score"],
    "phones.csv": ["id", "number"],
    "account_phone.csv": ["account_id", "phone_id"],
    "devices.csv": ["id", "device_fingerprint", "os"],
    "account_device.csv": ["account_id", "device_id", "first_seen", "last_seen"],
    "cashout_points.csv": ["id", "kind", "name", "location"],
    "transactions.csv": ["id", "amount", "timestamp", "channel", "status",
                         "sender_account_id", "receiver_account_id"],
    "paid_edges.csv": ["src", "dst", "amount", "timestamp", "txn_id"],
    "cashed_out_at.csv": ["account_id", "cashout_point_id", "amount", "timestamp"],
}

# Account ID range reserved for Phase 5 (mule + decoy accounts).
RESERVED_ACCOUNT_FIRST = 461  # ACC_0461
RESERVED_ACCOUNT_LAST = 500   # ACC_0500


class World:
    """Mutable collection of all generated entities + derived projections.

    Every attribute is a list of row dicts matching the HEADERS above. Lists are
    kept in insertion order so CSV output is deterministic.
    """

    def __init__(self):
        self.accounts = []
        self.phones = []
        self.account_phone = []
        self.devices = []
        self.account_device = []
        self.cashout_points = []
        self.transactions = []
        self.paid_edges = []
        self.cashed_out_at = []
        self.meta = {}

        # next free id sequence numbers (start at 1)
        self._seq = {"ACC": 1, "PH": 1, "DEV": 1, "TXN": 1, "COP": 1}

    # ---- id helpers ------------------------------------------------------
    def _next_id(self, prefix: str, width: int) -> str:
        n = self._seq[prefix]
        self._seq[prefix] += 1
        return f"{prefix}_{n:0{width}d}"

    def next_account_id(self) -> str:
        return self._next_id("ACC", 4)

    # ---- add helpers (Phase 5 entry points are on these) -----------------
    def add_account(self, holder_name, bank, account_type, opened_at,
                    balance_held, is_flagged, risk_score) -> str:
        """Append an account row and return its new id (ACC_....)."""
        aid = self.next_account_id()
        self.accounts.append({
            "id": aid, "holder_name": holder_name, "bank": bank,
            "account_type": account_type, "opened_at": int(opened_at),
            "balance_held": int(balance_held),
            "is_flagged": "true" if is_flagged else "false",
            "risk_score": int(risk_score),
        })
        return aid

    def add_device(self, device_fingerprint, os) -> str:
        did = self._next_id("DEV", 4)
        self.devices.append({"id": did, "device_fingerprint": device_fingerprint,
                             "os": os})
        return did

    def add_device_link(self, account_id, device_id, first_seen, last_seen) -> None:
        self.account_device.append({
            "account_id": account_id, "device_id": device_id,
            "first_seen": int(first_seen), "last_seen": int(last_seen),
        })

    def add_phone(self, number) -> str:
        pid = self._next_id("PH", 4)
        self.phones.append({"id": pid, "number": number})
        return pid

    def add_phone_link(self, account_id, phone_id) -> None:
        self.account_phone.append({"account_id": account_id, "phone_id": phone_id})

    def add_cashout_point(self, kind, name, location) -> str:
        cid = self._next_id("COP", 3)
        self.cashout_points.append({"id": cid, "kind": kind, "name": name,
                                    "location": location})
        return cid

    def add_transaction(self, sender, receiver, amount, timestamp, channel,
                        status="SUCCESS", cashout_point_id=None) -> str:
        """Add one Transaction + its projections.

        - sender/receiver are Account ids. For a cash-out (ATM) a receiver is the
          empty string and cashout_point_id names the CashOutPoint.
        - Inter-account transfers get a PAID shortcut edge mirroring the
          SENT -> Transaction -> RECEIVED_BY chain.
        - Cash-outs get a CASHED_OUT_AT row instead (money exits the system).
        """
        txn_id = self._next_id("TXN", 6)
        receiver = receiver if receiver is not None else ""
        self.transactions.append({
            "id": txn_id, "amount": int(amount), "timestamp": int(timestamp),
            "channel": channel, "status": status,
            "sender_account_id": sender, "receiver_account_id": receiver,
        })
        if cashout_point_id:
            self.cashed_out_at.append({
                "account_id": sender, "cashout_point_id": cashout_point_id,
                "amount": int(amount), "timestamp": int(timestamp),
            })
        else:
            self.paid_edges.append({
                "src": sender, "dst": receiver, "amount": int(amount),
                "timestamp": int(timestamp), "txn_id": txn_id,
            })
        return txn_id

    # ---- writing / loading ------------------------------------------------
    def write_all(self, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        payloads = {
            "accounts.csv": self.accounts,
            "phones.csv": self.phones,
            "account_phone.csv": self.account_phone,
            "devices.csv": self.devices,
            "account_device.csv": self.account_device,
            "cashout_points.csv": self.cashout_points,
            "transactions.csv": self.transactions,
            "paid_edges.csv": self.paid_edges,
            "cashed_out_at.csv": self.cashed_out_at,
        }
        for name in FILES:
            path = os.path.join(out_dir, name)
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=HEADERS[name])
                writer.writeheader()
                writer.writerows(payloads[name])
        import json
        with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh, indent=2, sort_keys=True)
            fh.write("\n")


def recompute_sequences(world: World) -> None:
    """Rebuild the _seq counters from the largest existing id per type."""
    for name, prefix in (("accounts", "ACC"), ("phones", "PH"),
                         ("devices", "DEV"), ("transactions", "TXN"),
                         ("cashout_points", "COP")):
        rows = getattr(world, name)
        if not rows:
            continue
        nums = [int(r["id"].split("_", 1)[1]) for r in rows]
        world._seq[prefix] = max(nums) + 1


def _reader(path):
    with open(path, newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


# columns holding epoch/amount integers (per CSV), reloaded as ints
INT_COLS = {
    "accounts": ("opened_at", "balance_held", "risk_score"),
    "account_device": ("first_seen", "last_seen"),
    "transactions": ("amount", "timestamp"),
    "paid_edges": ("amount", "timestamp"),
    "cashed_out_at": ("amount", "timestamp"),
}


def load_world_from_dir(data_dir: str) -> World:
    """Rebuild a World from already-written CSVs (for Phase 5 on-top extension)."""
    world = World()
    for name in FILES:
        attr = name[:-4]  # "accounts.csv" -> "accounts", etc.
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            continue
        rows = list(_reader(path))
        for col in INT_COLS.get(attr, ()):
            for r in rows:
                if r.get(col) not in (None, ""):
                    r[col] = int(r[col])
        setattr(world, attr, rows)
    meta_path = os.path.join(data_dir, "meta.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, encoding="utf-8") as fh:
            world.meta = json.load(fh)
    recompute_sequences(world)
    return world