from __future__ import annotations
import json
import logging
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

from src.config import get_settings

logger = logging.getLogger(__name__)

FLOOR_PLAN_PATH = os.path.join(os.path.dirname(__file__), "../../data/floor_plan.json")
FLOOR_PLAN_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "../data/floor_plan.default.json")


def _get_dsn() -> str:
    s = get_settings()
    return (
        f"host={s.env.postgres_host} port={s.env.postgres_port} "
        f"dbname={s.env.postgres_db} user={s.env.postgres_user} "
        f"password={s.env.postgres_password}"
    )


@contextmanager
def _get_conn():
    """Context manager for DB connections — prevents leaks on exceptions."""
    conn = psycopg2.connect(_get_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_assignments_table() -> None:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS floor_plan_assignments (
                        id            SERIAL PRIMARY KEY,
                        table_id      TEXT NOT NULL,
                        reservation_id TEXT NOT NULL,
                        date          DATE NOT NULL,
                        hour          TEXT NOT NULL,
                        UNIQUE(table_id, date, hour),
                        UNIQUE(reservation_id, date, hour)
                    )
                """)
    except Exception as exc:
        logger.warning("[HostAI] - Floor Plan: ensure_assignments_table failed: %s", exc)


def get_floor_plan() -> dict:
    for path in (FLOOR_PLAN_PATH, FLOOR_PLAN_DEFAULT_PATH):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            continue
    return {"tables": []}


def save_floor_plan(layout: dict) -> None:
    os.makedirs(os.path.dirname(FLOOR_PLAN_PATH), exist_ok=True)
    with open(FLOOR_PLAN_PATH, "w") as f:
        json.dump(layout, f, indent=2)


def get_assignments(date: str, hour: str | None = None) -> list[dict]:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                if hour:
                    cur.execute(
                        "SELECT table_id, reservation_id, date::text, hour FROM floor_plan_assignments WHERE date=%s AND hour=%s",
                        (date, hour),
                    )
                else:
                    cur.execute(
                        "SELECT table_id, reservation_id, date::text, hour FROM floor_plan_assignments WHERE date=%s",
                        (date,),
                    )
                rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def assign_table(table_id: str, reservation_id: str, date: str, hour: str) -> dict:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO floor_plan_assignments (table_id, reservation_id, date, hour)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (table_id, date, hour) DO UPDATE
                  SET reservation_id = EXCLUDED.reservation_id
                RETURNING table_id, reservation_id, date::text, hour
                """,
                (table_id, reservation_id, date, hour),
            )
            row = cur.fetchone()
        return dict(row)


def unassign_table(reservation_id: str, date: str, hour: str) -> bool:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM floor_plan_assignments WHERE reservation_id=%s AND date=%s AND hour=%s",
                (reservation_id, date, hour),
            )
            deleted = cur.rowcount
        return deleted > 0
