"""Base-world transactions (normal, non-fraud money movement).

Produces ~budget transactions over the 30-day window with realistic behaviour:
  * log-normal amounts (many small, few large, in rupees)
  * a daily time-of-day pattern (peak 10:00-22:00, quiet at night)
  * channels mostly UPI with some IMPS / NEFT
  * individual-to-merchant payments dominate; merchant popularity is skewed
    (a few very busy, most quiet)
  * person-to-person transfers within small social circles (3-8 usual contacts)
  * monthly salary-style credits and rent-style recurring payments
  * a small number of legitimate rapid multi-hop forwards (A -> B -> C within
    minutes) so rapid hopping alone is NOT proof of fraud
  * legitimate ATM withdrawals by a few accounts

Every inter-account transfer becomes a Transaction + a PAID shortcut edge. ATM
withdrawals become a Transaction (channel=ATM, no receiver) + a CASHED_OUT_AT row.
"""
from __future__ import annotations

import math

from . import cashout as cashout_mod

# ---------------------------------------------------------------------------
# Daily activity pattern: 24 hourly weights, peak 10:00-22:00.
# ---------------------------------------------------------------------------
HOUR_WEIGHTS = [
    # 0     1     2     3     4     5     6     7
    0.02, 0.01, 0.01, 0.01, 0.01, 0.02, 0.05, 0.12,
    # 8     9     10    11    12    13    14    15
    0.20, 0.30, 0.45, 0.55, 0.60, 0.55, 0.50, 0.55,
    # 16    17    18    19    20    21    22    23
    0.55, 0.70, 0.90, 0.95, 0.85, 0.55, 0.35, 0.15,
]

BUDGET = 5000                       # default transaction budget (scaled by --scale)
# share of the budget for each behaviour (sums to 1.0 of the non-merchant mix;
# merchant purchases take whatever remains to hit the budget exactly)
SALARY_SHARE = 137 / 5000
RENT_SHARE = 86 / 5000
ATM_SHARE = 60 / 5000
P2P_SHARE = 1176 / 5000
RAPID_PATTERNS = 12
ATM_ACCOUNTS = 25                   # how many distinct accounts withdraw cash


def generate(world, rng, window_start, window_end, budget=BUDGET):
    """Populate world.transactions, world.paid_edges and world.cashed_out_at."""
    individuals = [a for a in world.accounts if a["account_type"] == "individual"]
    merchants = [a for a in world.accounts if a["account_type"] == "merchant"]
    ind_ids = [a["id"] for a in individuals]
    mer_ids = [a["id"] for a in merchants]

    n_sal = max(0, round(budget * SALARY_SHARE))
    n_rent = max(0, round(budget * RENT_SHARE))
    n_atm = max(0, round(budget * ATM_SHARE))
    n_p2p = max(0, round(budget * P2P_SHARE))
    n_rapid = max(6, min(RAPID_PATTERNS, budget // 2))
    fixed = n_sal + n_rent + n_atm + n_p2p + n_rapid * 2
    n_merchant = max(0, budget - fixed)

    # ---- social circles: each individual has 3-8 usual contacts ----------
    contacts = {a: [] for a in ind_ids}
    for a in ind_ids:
        others = [i for i in ind_ids if i != a]
        rng.shuffle(others)
        contacts[a] = others[:rng.randint(3, 8)]

    # ---- helper builders --------------------------------------------------
    def random_ts(horizon_end=window_end):
        day = rng.randint(0, 29)
        hour = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
        return int(window_start + day * 86_400 + hour * 3600
                   + rng.randint(0, 59) * 60 + rng.randint(0, 59))

    def lognorm(mu, sigma, cap):
        return max(1, min(int(round(rng.lognormvariate(mu, sigma))), cap))

    def channel():
        return rng.choices(["UPI", "IMPS", "NEFT"], weights=[0.80, 0.13, 0.07])[0]

    def event(sender, receiver, amount, timestamp, ch, cop=None):
        return {"sender": sender, "receiver": receiver, "amount": amount,
                "timestamp": timestamp, "channel": ch,
                "cashout_point_id": cop}

    events = []

    # ---- salary-style monthly credits (employer merchant -> employee) ----
    if n_sal:
        employees = rng.sample(ind_ids, n_sal)
        employers = rng.sample(mer_ids, min(12, len(mer_ids)))
        for emp in employees:
            amount = lognorm(math.log(45_000), 0.5, 250_000)
            day = rng.randint(1, 30)
            hour = rng.randint(8, 10)
            ts = int(window_start + (day - 1) * 86_400 + hour * 3600
                     + rng.randint(0, 59) * 60 + rng.randint(0, 59))
            events.append(event(rng.choice(employers), emp, amount, ts, "IMPS"))

    # ---- rent-style recurring payments (renter -> landlord) --------------
    if n_rent:
        renters = rng.sample(ind_ids, n_rent)
        for renter in renters:
            landlord = rng.choice([i for i in ind_ids if i != renter])
            amount = lognorm(math.log(18_000), 0.5, 150_000)
            day = rng.randint(1, 6)
            hour = rng.randint(6, 9)
            ts = int(window_start + (day - 1) * 86_400 + hour * 3600
                     + rng.randint(0, 59) * 60 + rng.randint(0, 59))
            events.append(event(renter, landlord, amount, ts,
                                "NEFT" if amount > 100_000 else "UPI"))

    # ---- legitimate rapid multi-hop forwards (A -> B -> C in minutes) ----
    for _ in range(n_rapid):
        a = rng.choice(ind_ids)
        b = rng.choice(contacts[a])
        candidates = [c for c in contacts[b] if c != a]
        c = rng.choice(candidates) if candidates else \
            rng.choice([i for i in ind_ids if i not in (a, b)])
        amt_a = lognorm(math.log(12_000), 0.7, 150_000)
        ts_a = rng.randint(window_start, window_end - 600)
        ts_b = ts_a + rng.randint(60, 600)
        amt_b = int(round(amt_a * rng.uniform(0.5, 0.95)))
        events.append(event(a, b, amt_a, ts_a, "UPI"))
        events.append(event(b, c, amt_b, ts_b, "UPI"))

    # ---- person-to-person transfers within social circles ----------------
    for _ in range(n_p2p):
        sender = rng.choice(ind_ids)
        receiver = rng.choice(contacts[sender])
        amount = lognorm(math.log(3600), 0.9, 200_000)
        events.append(event(sender, receiver, amount, random_ts(), channel()))

    # ---- legitimate ATM withdrawals by a few accounts --------------------
    if n_atm:
        atm_ids = cashout_mod.atm_ids(world)
        atm_users = rng.sample(ind_ids, min(ATM_ACCOUNTS, len(ind_ids)))
        for _ in range(n_atm):
            amount = lognorm(math.log(5000), 0.5, 20_000)
            # withdrawals happen during waking hours
            day = rng.randint(0, 29)
            hour = rng.choices(range(8, 23), weights=HOUR_WEIGHTS[8:23])[0]
            ts = int(window_start + day * 86_400 + hour * 3600
                     + rng.randint(0, 59) * 60 + rng.randint(0, 59))
            events.append(event(rng.choice(atm_users), None, amount, ts, "ATM",
                                cop=rng.choice(atm_ids)))

    # ---- individual-to-merchant purchases (skewed popularity) ------------
    if n_merchant:
        rng.shuffle(mer_ids)
        # gentle power-law: a few busy merchants, most quiet, none absurdly dominant
        popularity = [(i + 1) ** -0.6 for i in range(len(mer_ids))]
        venders = rng.choices(mer_ids, weights=popularity, k=n_merchant)
        for merchant in venders:
            buyer = rng.choice(ind_ids)
            amount = lognorm(math.log(1500), 0.9, 100_000)
            events.append(event(buyer, merchant, amount, random_ts(), channel()))

    # ---- commit in time order --------------------------------------------
    events.sort(key=lambda e: (e["timestamp"],))
    for e in events:
        world.add_transaction(
            sender=e["sender"], receiver=e["receiver"], amount=e["amount"],
            timestamp=e["timestamp"], channel=e["channel"], status="SUCCESS",
            cashout_point_id=e["cashout_point_id"],
        )

    world.meta["budget"] = budget
    world.meta["n_salary"] = n_sal
    world.meta["n_rent"] = n_rent
    world.meta["n_atm"] = n_atm
    world.meta["n_p2p"] = n_p2p
    world.meta["n_rapid_patterns"] = n_rapid
    world.meta["n_merchant"] = n_merchant