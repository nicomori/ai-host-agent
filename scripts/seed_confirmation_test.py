"""Seed 40 test reservations over the next 10 days with Nicolas's phone number."""
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.services import db as pg_db

PHONE = "+4915750441601"
NAMES = [
    "Nicolas Mori", "Marco Rossi", "Laura Bianchi", "Giovanni Romano",
    "Elena Morelli", "Paolo Conti", "Valentina Galli", "Diego Fontana",
    "Chiara Monelli", "Luca Barbieri", "Sofia De Luca", "Andrea Mancini",
    "Giulia Martini", "Matteo Esposito", "Alessandra Lombardi", "Carlo Gatti",
    "Marta Bertoni", "Federico Ricci", "Sara Colombo", "Roberto Marchetti",
]
PREFS = [None, "Patio", "Window", "Quiet Corner", "Bar View", "Booth", "Private Table", "Near Kitchen"]
TIMES_LUNCH = ["12:00", "12:30", "13:00", "13:30", "14:00"]
TIMES_DINNER = ["19:00", "19:30", "20:00", "20:30", "21:00", "21:30", "22:00"]

def main():
    from datetime import date, timedelta

    pg_db.init_db()
    today = date.today()
    total = 0

    for day_offset in range(1, 11):
        d = today + timedelta(days=day_offset)
        count = 4  # 4 per day * 10 days = 40
        for _ in range(count):
            name = random.choice(NAMES)
            time = random.choice(TIMES_LUNCH + TIMES_DINNER)
            party = random.choices([2, 3, 4, 5, 6], weights=[40, 25, 20, 10, 5])[0]
            pref = random.choice(PREFS)
            pg_db.save_reservation(
                guest_name=name,
                guest_phone=PHONE,
                date=str(d),
                time=time,
                party_size=party,
                preference=pref,
                notes=f"Test reservation for confirmation flow",
            )
            total += 1
            print(f"  {d} {time} — {name} ({party}p) pref={pref or 'none'}")

    print(f"\nSeeded {total} reservations over 10 days with phone {PHONE}")

if __name__ == "__main__":
    main()
