"""Base-world cash-out points (ATMs, crypto exchanges, wallets).

Only the ATMs get used in the normal world (legitimate withdrawals). The crypto
exchanges and wallets are declared here so they exist in the graph, but normal
accounts never interact with them -- Phase 5's mule rings cash out through them.
"""
from __future__ import annotations

N_ATMS = 15
N_CRYPTO = 3
N_WALLETS = 2

ATMS = [
    "State Bank ATM - MG Road", "HDFC ATM - Koramangala", "ICICI ATM - Indiranagar",
    "Axis ATM - Whitefield", "PNB ATM - Jayanagar", "Kotak ATM - HSR Layout",
    "BoB ATM - Marathahalli", "Canara ATM - Malleshwaram", "Union ATM - South End",
    "SBI ATM - Banashankari", "HDFC ATM - Electronic City", "ICICI ATM - Yelahanka",
    "Axis ATM - Chruch Street", "SBI ATM - Andheri", "HDFC ATM - Connaught Place",
]
ATM_LOCATIONS = [
    "Bengaluru", "Bengaluru", "Bengaluru", "Bengaluru", "Bengaluru",
    "Bengaluru", "Bengaluru", "Bengaluru", "Bengaluru", "Bengaluru",
    "Bengaluru", "Bengaluru", "Bengaluru", "Mumbai", "New Delhi",
]
CRYPTO = [
    ("Kaleido Exchange", "Mumbai"),
    ("Orbit Crypto Exchange", "Gurugram"),
    ("VaultX Exchange", "Bengaluru"),
]
WALLETS = [
    ("DigiPay Wallet", "Bengaluru"),
    ("SuperCoin Wallet", "Pune"),
]


def generate(world, rng):
    """Populate world.cashout_points. ATMs first, then crypto, then wallets."""
    for name, loc in zip(ATMS, ATM_LOCATIONS):
        world.add_cashout_point("ATM", name, loc)
    for name, loc in CRYPTO:
        world.add_cashout_point("CRYPTO_EXCHANGE", name, loc)
    for name, loc in WALLETS:
        world.add_cashout_point("WALLET", name, loc)
    world.meta["n_atms"] = N_ATMS
    world.meta["n_crypto"] = N_CRYPTO
    world.meta["n_wallets"] = N_WALLETS


def atm_ids(world):
    return [c["id"] for c in world.cashout_points if c["kind"] == "ATM"]