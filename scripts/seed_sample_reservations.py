#!/usr/bin/env python3
"""
Seed script — populate ai-host-agent with ~30 sample reservations per day with preferences.

Usage:
  cd /Users/nicolasmori/personal-projects/ai-host-agent
  python3 scripts/seed_sample_reservations.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services import db as pg_db
from src.config import get_settings

# Sample data
FIRST_NAMES = [
    "Marco", "Giulia", "Luca", "Francesca", "Andrea", "Maria", "Giovanni", "Elena",
    "Paolo", "Alessandra", "Roberto", "Silvia", "Davide", "Sofia", "Matteo", "Francesca",
    "Carlo", "Laura", "Antonio", "Valentina", "Giuseppe", "Rosa", "Diego", "Chiara",
    "Filippo", "Martina", "Riccardo", "Giuliana", "Stefano", "Marta",
]

LAST_NAMES = [
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Colombo", "Ricci", "Romano",
    "Marino", "Gallo", "Conti", "De Luca", "Mancini", "Costa", "Fontana", "Moretti",
    "Villa", "Ferrara", "Rinaldi", "Barbieri", "Marchi", "Lombardi", "Carletti", "Gatti",
]

PREFERENCES = [
    "Patio",
    "Window",
    "Quiet Corner",
    "Bar View",
    "Booth",
    "Private Table",
    "Near Kitchen",
    "High Seating",
    "Low Lighting",
    None,  # No preference
]

PHONE_PREFIXES = [
    "+39 06",    # Rome
    "+39 02",    # Milan
    "+39 10",    # Genoa
    "+39 81",    # Naples
    "+39 95",    # Catania
]

SPECIAL_REQUESTS = [
    "Birthday celebration, need candles",
    "Anniversary dinner",
    "Business meeting",
    "Dietary restrictions - vegetarian",
    "Dietary restrictions - gluten-free",
    "Celebrating promotion",
    "First date",
    "Family gathering",
    "High chair needed for baby",
    None,
]


def generate_sample_reservations(date_str: str, count: int = 30) -> list[dict]:
    """Generate ~30 sample reservations for a given date."""
    import random
    import uuid

    reservations = []

    # Spread reservations across lunch (12:00-14:00) and dinner (19:00-23:00)
    lunch_hours = ["12:00", "12:15", "12:30", "12:45", "13:00", "13:15", "13:30", "13:45", "14:00"]
    dinner_hours = ["19:00", "19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45", "21:00", "21:30", "22:00", "22:30"]

    hours = lunch_hours + dinner_hours

    for i in range(count):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        guest_name = f"{first_name} {last_name}"

        phone_prefix = random.choice(PHONE_PREFIXES)
        phone_number = f"{phone_prefix} {random.randint(1000000, 9999999)}"

        party_size = random.choices(
            [1, 2, 3, 4, 5, 6, 8],
            weights=[2, 30, 25, 20, 15, 5, 3]  # Most common: 2-3 people
        )[0]

        hour = random.choice(hours)

        preference = random.choice(PREFERENCES)
        special_request = random.choice(SPECIAL_REQUESTS)

        reservations.append({
            "guest_name": guest_name,
            "guest_phone": phone_number,
            "date": date_str,
            "time": hour,
            "party_size": party_size,
            "preference": preference,
            "special_requests": special_request,
            "notes": None,
            "reservation_id": str(uuid.uuid4()),
        })

    return reservations


def seed_database():
    """Initialize DB and populate with sample reservations."""
    print("🍝 HostAI Sample Data Seed Script")
    print("=" * 60)

    # Initialize schema
    print("\n1️⃣  Initializing PostgreSQL schema...")
    pg_db.init_db()
    print("   ✅ Schema initialized")

    # Get today's date
    today = datetime.now().date()

    # Generate and insert reservations for today and tomorrow
    dates_to_seed = [
        today,
        today + timedelta(days=1),
    ]

    total_saved = 0

    for seed_date in dates_to_seed:
        date_str = seed_date.strftime("%Y-%m-%d")
        print(f"\n2️⃣  Generating 30 sample reservations for {date_str}...")

        reservations = generate_sample_reservations(date_str, count=30)

        saved_count = 0
        for res in reservations:
            try:
                pg_db.save_reservation(
                    guest_name=res["guest_name"],
                    guest_phone=res["guest_phone"],
                    date=res["date"],
                    time=res["time"],
                    party_size=res["party_size"],
                    reservation_id=res["reservation_id"],
                    preference=res["preference"],
                    special_requests=res["special_requests"],
                    notes=res["notes"],
                )
                saved_count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to save {res['guest_name']}: {e}")

        print(f"   ✅ Saved {saved_count}/{len(reservations)} reservations for {date_str}")
        total_saved += saved_count

    print(f"\n✨ Seed complete!")
    print(f"   Total reservations saved: {total_saved}")
    print(f"\n📊 Summary:")
    all_reservations = pg_db.list_reservations()
    print(f"   Total reservations in database: {len(all_reservations)}")

    # Show distribution by preference
    preferences_count = {}
    for res in all_reservations:
        pref = res.get("preference") or "None"
        preferences_count[pref] = preferences_count.get(pref, 0) + 1

    print(f"\n   Preferences distribution:")
    for pref, count in sorted(preferences_count.items(), key=lambda x: -x[1]):
        print(f"     • {pref}: {count} reservations")

    print(f"\n🚀 Ready! Run the backend server and visit http://localhost:5173 to see the dashboard.")


if __name__ == "__main__":
    seed_database()
