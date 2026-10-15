"""Base-world devices and account->device usage.

Most accounts use 1 device, a minority use 2. About 6% of devices are shared by
2-3 accounts (families, shared office handsets). Shared devices are intentional
noise: a shared device is NOT proof of fraud, so the demo is not too clean and
`find_shared_devices` has background activity to be confused with.

Fingerprints are deterministic unique strings; os is mostly android.
"""
from __future__ import annotations

# share of accounts given a second personal device
PCT_TWO_DEVICES = 0.18
# ~6% of devices are shared by 2-3 accounts -> build these many shared devices
NUM_SHARED_DEVICES = 33
# how the shared devices are split: 27 groups of 2 + 6 groups of 3 accounts
SHARED_SIZES = [2] * 27 + [3] * 6
OS = ["android", "android", "android", "ios"]  # 75% android


def generate(world, rng, window_start, window_end):
    """Populate world.devices and world.account_device (pure base world)."""
    account_ids = [a["id"] for a in world.accounts]
    opened = {a["id"]: a["opened_at"] for a in world.accounts}

    def fingerprint():
        while True:
            fp = "DF-" + format(rng.getrandbits(56), "014x")
            if not any(d["device_fingerprint"] == fp for d in world.devices):
                return fp

    def new_device_link(acc_id, first_seen, last_seen):
        dev_id = world.add_device(fingerprint(), rng.choice(OS))
        world.add_device_link(acc_id, dev_id, first_seen, last_seen)
        return dev_id

    def usage_window(acc_id):
        last_seen = window_start + rng.randint(0, int(window_end - window_start))
        return opened[acc_id], last_seen

    # ---- personal devices: 1 normally, 2 for a minority ------------------
    rng.shuffle(account_ids)
    two_devices = set(account_ids[:round(len(account_ids) * PCT_TWO_DEVICES)])
    for acc_id in account_ids:
        n_devices = 2 if acc_id in two_devices else 1
        for _ in range(n_devices):
            new_device_link(acc_id, *usage_window(acc_id))

    # ---- shared devices: 2-3 accounts per device -------------------------
    rng.shuffle(account_ids)
    shared_accounts = account_ids[:sum(SHARED_SIZES)]  # first 72 accounts
    idx = 0
    for size in SHARED_SIZES:
        group = shared_accounts[idx:idx + size]
        idx += size
        # a shared device is fresh; give it its own observation window too
        dev_id = new_device_link(group[0], *usage_window(group[0]))
        for acc_id in group[1:]:
            world.add_device_link(acc_id, dev_id, *usage_window(acc_id))


def shared_device_stats(world):
    """Return (num shared devices, num accounts involved)."""
    use = {}
    for r in world.account_device:
        use.setdefault(r["device_id"], set()).add(r["account_id"])
    shared = {d: a for d, a in use.items() if len(a) >= 2}
    involved = set().union(*shared.values()) if shared else set()
    return len(shared), len(involved)