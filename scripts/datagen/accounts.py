"""Base-world accounts, phones and their registrations.

Generates ~BASE_ACCOUNTS accounts (monly individual with a few merchants), one
registered phone per account with a few (~2%) shared by family members, realistic
Indian names and a spread of banks / open dates / balances.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
BASE_ACCOUNTS = 460          # base-world accounts (ACC_0001..ACC_0460)
INDIVIDUAL_FRACTION = 0.85   # ~85% individual, ~15% merchant
SHARED_PHONE_PAIRS = 5       # ~2% of accounts share a phone (10 accounts, 5 pairs)

BANKS = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
    "Punjab National Bank", "Kotak Mahindra Bank", "Bank of Baroda",
    "Canara Bank", "Union Bank of India", "Yes Bank",
]

MERCHANT_CATEGORIES = [
    "General Store", "Supermarket", "Pharmacy", "Electronics", "Textiles",
    "Restaurant", "Grocery", "Hardware", "Furniture", "Stationery",
    "Mobile Care", "Auto Garage", "Dairy", "Bakery", "Tailoring",
    "Salon", "Physiotherapy", "Computer Hub", "Bookshop", "Sports Goods",
    "Home Appliances", "Gift House", "Opticals", "Courier Services", "Jewellers",
]
INDIAN_SURNAMES = [
    "Sharma", "Patel", "Gupta", "Singh", "Iyer", "Reddy", "Khan", "Verma",
    "Nair", "Mehta", "Joshi", "Das", "Menon", "Rao", "Chauhan", "Kulkarni",
    "Desai", "Banerjee", "Agarwal", "Shetty", "Mishra", "Pillai", "Naidu",
    "Bhat", "Kapoor", "Saxena", "Trivedi", "Ghosh", "Hegde", "Prakash",
]


def _individual_balance(rng) -> int:
    """Mostly small balances, a few large; rs, integer, >= 0."""
    if rng.random() < 0.04:  # a few wealthier people
        v = rng.lognormvariate(math.log(1_800_000), 0.9)
    else:
        v = rng.lognormvariate(math.log(16_000), 1.05)
    return max(0, min(int(round(v)), 8_000_000))


def _merchant_balance(rng) -> int:
    v = rng.lognormvariate(math.log(350_000), 1.1)
    return max(20_000, min(int(round(v)), 40_000_000))


def _merchant_name(rng) -> str:
    surname = rng.choice(INDIAN_SURNAMES)
    category = rng.choice(MERCHANT_CATEGORIES)
    if rng.random() < 0.25:
        return f"Sri {surname} {category}"
    return f"{surname} {category}"


def generate(world, faker, rng, now_epoch):
    """Populate world.accounts, world.phones and world.account_phone."""
    n_ind = round(BASE_ACCOUNTS * INDIVIDUAL_FRACTION)
    n_mer = BASE_ACCOUNTS - n_ind

    def phone_number():
        # en_IN's phone provider is inconsistent, so build a clean +91 mobile
        return f"+91 9{rng.randint(0, 9999):04d} {rng.randint(0, 99999):05d}"

    # -- individuals (names from en_IN Faker, seeded => reproducible) -------
    for _ in range(n_ind):
        world.add_account(
            holder_name=faker.name(),
            bank=rng.choice(BANKS),
            account_type="individual",
            opened_at=_random_open_time(rng, now_epoch),
            balance_held=_individual_balance(rng),
            is_flagged=False,
            risk_score=0,
        )

    # -- merchants ----------------------------------------------------------
    for _ in range(n_mer):
        world.add_account(
            holder_name=_merchant_name(rng),
            bank=rng.choice(BANKS),
            account_type="merchant",
            opened_at=_random_open_time(rng, now_epoch),
            balance_held=_merchant_balance(rng),
            is_flagged=False,
            risk_score=0,
        )

    # -- one registered phone per account ----------------------------------
    phones = []  # (account_id, phone_id)
    for acc in world.accounts:
        pid = world.add_phone(phone_number())
        world.add_phone_link(acc["id"], pid)
        phones.append((acc["id"], pid))

    # -- a few accounts share a phone (family), removing the now-unused phone
    shared = rng.sample([a for a, _ in phones], 2 * SHARED_PHONE_PAIRS)
    for i in range(SHARED_PHONE_PAIRS):
        a_keep, a_family = shared[2 * i], shared[2 * i + 1]
        keep_phone = next(p for a, p in phones if a == a_keep)
        drop_phone = next(p for a, p in phones if a == a_family)
        # remove the family account's unique phone link + its phone row
        world.account_phone = [r for r in world.account_phone
                               if not (r["account_id"] == a_family and r["phone_id"] == drop_phone)]
        world.phones = [r for r in world.phones if r["id"] != drop_phone]
        # point the family account at the shared (keep) phone
        world.account_phone.append({"account_id": a_family, "phone_id": keep_phone})

    world.meta["n_individuals"] = n_ind
    world.meta["n_merchants"] = n_mer


def _random_open_time(rng, now_epoch) -> int:
    """opened_at spread over 1..8 years before now (all before the 30-day window)."""
    years = 1 + rng.random() * 7            # 1.0 .. 8.0 years ago
    days = years * 365
    return int(now_epoch - days * 86_400)