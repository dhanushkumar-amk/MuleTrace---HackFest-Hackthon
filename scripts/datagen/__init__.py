"""MuleTrace synthetic data generator package.

Entry points used by Phase 5 to extend the base world:

    world = datagen.build_base_world(seed=7, scale=1.0)
    # or datagen.load_world_from_dir("data/generated") to extend existing files
    ...
    world.write_all("data/generated")

Seed + a fixed clock make the output fully reproducible regardless of run date.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta

from faker import Faker

from .world import World, load_world_from_dir  # noqa: F401
from . import accounts as _accounts
from . import devices as _devices
from . import cashout as _cashout
from . import transactions as _transactions

# Fixed "now" for the whole dataset: 2026-10-15 12:00 IST. The 30-day demo window
# ends here, so epoch timestamps are stable across runs.
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=IST)
WINDOW_DAYS = 30
WINDOW_SEC = WINDOW_DAYS * 86_400
WINDOW_END = int(NOW.timestamp())
WINDOW_START = WINDOW_END - WINDOW_SEC

# where data/ artifacts live relative to the repo root (muletrace/)
REPO_ROOT = __path__[0].rsplit("scripts", 1)[0]


def build_base_world(seed: int = 7, scale: float = 1.0) -> World:
    """Build the normal (non-fraud) base world end to end.

    Pure function of (seed, scale): identical inputs give identical CSVs. Nothing
    is written until the caller calls world.write_all(out_dir).
    """
    Faker.seed(seed)
    faker = Faker("en_IN")
    faker.seed_instance(seed)
    rng = random.Random(seed)

    world = World()
    world.meta.update({
        "seed": seed,
        "scale": scale,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "window_start_iso": _iso(WINDOW_START),
        "window_end_iso": _iso(WINDOW_END),
        "window_days": WINDOW_DAYS,
        "base_accounts": _accounts.BASE_ACCOUNTS,
        "now_iso": _iso(WINDOW_END),
    })

    _accounts.generate(world, faker, rng, WINDOW_END)
    _devices.generate(world, rng, WINDOW_START, WINDOW_END)
    _cashout.generate(world, rng)
    budget = max(1, round(_transactions.BUDGET * scale))
    _transactions.generate(world, rng, WINDOW_START, WINDOW_END, budget=budget)

    world.meta["n_accounts"] = len(world.accounts)
    world.meta["n_transactions"] = len(world.transactions)
    return world


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=IST).isoformat()