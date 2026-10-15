"""Generate MuleTrace's synthetic NORMAL (non-fraud) base world.

Writes plain CSVs into data/generated/ (one per entity type) plus a meta.json
describing the 30-day window, plus a committed tiny sample into data/sample/.

Phase 5 builds fraud on top of this via the `world.build/load + add_*` interface
documented in scripts/datagen/world.py -- it does NOT regenerate the base world.

Usage:
    python scripts/generate_data.py                 # default seed=7, scale=1.0
    python scripts/generate_data.py --seed 42 --scale 1.5
    python scripts/generate_data.py --out /tmp/gen

ID ranges (stability + Phase 5 reservation):
    ACC_0001..ACC_0460  base-world accounts
    ACC_0461..ACC_0500  RESERVED for Phase 5 (mule + decoy accounts; 40 slots)
    PH_/DEV_/TXN_/COP_  continue automatically from the base world's last ID
"""
from __future__ import annotations

import argparse
import os
import sys

# allow `python scripts/generate_data.py` from anywhere in the repo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen import build_base_world, REPO_ROOT  # noqa: E402
from datagen.world import FILES, HEADERS, RESERVED_ACCOUNT_FIRST, RESERVED_ACCOUNT_LAST  # noqa: E402

DEFAULT_OUT = os.path.join(REPO_ROOT, "data", "generated")
SAMPLE_DIR = os.path.join(REPO_ROOT, "data", "sample")
SAMPLE_ROWS = 20


def write_samples(world) -> None:
    """Write the first SAMPLE_ROWS of each CSV so the repo shows the shape."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    for name in FILES:
        attr = name[:-4]
        rows = getattr(world, attr)
        path = os.path.join(SAMPLE_DIR, name)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            import csv
            writer = csv.DictWriter(fh, fieldnames=HEADERS[name])
            writer.writeheader()
            writer.writerows(rows[:SAMPLE_ROWS])
    with open(os.path.join(SAMPLE_DIR, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "# data/sample\n\n"
            f"First {SAMPLE_ROWS} rows of each generated file (from `scripts/generate_data.py`).\n"
            "Run `scripts/validate_data.py` for counts and PASS/FAIL checks.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7, help="random seed (default 7)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="multiplier for the transaction budget (default 1.0)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args()

    world = build_base_world(seed=args.seed, scale=args.scale)
    world.write_all(args.out)
    if os.path.abspath(args.out) == os.path.abspath(DEFAULT_OUT):
        write_samples(world)

    ms = world.meta
    print(f"== wrote base world (seed={args.seed}, scale={args.scale}) to {args.out}")
    print(f"   accounts={ms['n_accounts']}  transactions={ms['n_transactions']}  "
          f"window={ms['window_start_iso']} .. {ms['window_end_iso']}")
    print(f"   breakdown: salary={ms['n_salary']} rent={ms['n_rent']} atm={ms['n_atm']} "
          f"p2p={ms['n_p2p']} rapid_patterns={ms['n_rapid_patterns']} "
          f"merchant={ms['n_merchant']}")
    print(f"   reserved for Phase 5: ACC_{RESERVED_ACCOUNT_FIRST:04d}"
          f"..ACC_{RESERVED_ACCOUNT_LAST:04d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())