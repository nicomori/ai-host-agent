#!/usr/bin/env python3
"""
Seed script — populate ai-host-agent with 150 sample reservations from fixture JSON.

Usage:
  cd /Users/nicolasmori/personal-projects/ai-host-agent
  python3 scripts/seed_sample_reservations.py
"""

import json
import sys
import uuid
from pathlib import Path

# Add src to path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services import db as pg_db
from src.config import get_settings

FIXTURE_PATH = project_root / "e2e" / "fixtures" / "seed-reservations.json"


def seed_database():
    """Initialize DB and populate with sample reservations from fixture JSON."""
    print("HostAI Sample Data Seed Script")
    print("=" * 60)

    # Initialize schema
    print("\n1. Initializing PostgreSQL schema...")
    pg_db.init_db()
    print("   Schema initialized")

    # Load fixture data
    print(f"\n2. Loading fixture data from {FIXTURE_PATH}...")
    with open(FIXTURE_PATH, "r") as f:
        reservations = json.load(f)
    print(f"   Loaded {len(reservations)} reservations")

    # Insert reservations
    total_saved = 0
    dates_count: dict[str, int] = {}

    for res in reservations:
        try:
            pg_db.save_reservation(
                guest_name=res["guest_name"],
                guest_phone=res["guest_phone"],
                date=res["date"],
                time=res["time"],
                party_size=res["party_size"],
                reservation_id=str(uuid.uuid4()),
                preference=res.get("preference"),
                special_requests=res.get("special_requests"),
                notes=res.get("notes"),
            )
            total_saved += 1
            dates_count[res["date"]] = dates_count.get(res["date"], 0) + 1
        except Exception as e:
            print(f"   Warning: Failed to save {res['guest_name']}: {e}")

    print(f"\n3. Seed complete!")
    print(f"   Total reservations saved: {total_saved}/{len(reservations)}")

    print(f"\n   Distribution by date:")
    for date_str in sorted(dates_count.keys()):
        print(f"     {date_str}: {dates_count[date_str]} reservations")

    # Show distribution by preference
    all_reservations = pg_db.list_reservations()
    preferences_count: dict[str, int] = {}
    for res in all_reservations:
        pref = res.get("preference") or "None"
        preferences_count[pref] = preferences_count.get(pref, 0) + 1

    print(f"\n   Preferences distribution:")
    for pref, count in sorted(preferences_count.items(), key=lambda x: -x[1]):
        print(f"     {pref}: {count} reservations")

    print(f"\n   Ready! Run the backend server and visit http://localhost:5173")


if __name__ == "__main__":
    seed_database()
