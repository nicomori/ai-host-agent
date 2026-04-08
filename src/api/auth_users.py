"""
User authentication — HostAI (ai-host-agent).
JWT-based auth with bcrypt password hashing and role-based access control.

Roles:
  admin  — full access: view + write + manage users
  writer — can create/update reservations, seat guests
  reader — view only (GET endpoints)
"""
from __future__ import annotations

import bcrypt
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

import logging
import os
from contextlib import contextmanager

from src.config import get_settings

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ha-jwt-secret-2026-changeme")
ALGORITHM  = "HS256"
TOKEN_TTL_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# ─── Models ──────────────────────────────────────────────────────────────────

class UserInfo(BaseModel):
    username: str
    role: str
    can_edit_floor_plan: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "reader"


class UpdatePermissionsRequest(BaseModel):
    can_edit_floor_plan: bool


# ─── DB helpers ──────────────────────────────────────────────────────────────

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


def _get_user(username: str) -> Optional[dict]:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM app_users WHERE username=%s", (username,))
                row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _list_users() -> list[dict]:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, role, can_edit_floor_plan, created_at FROM app_users ORDER BY id")
                rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def ensure_default_users() -> None:
    """Create app_users table and seed admin/writer/reader if they don't exist."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS app_users (
                        id            SERIAL PRIMARY KEY,
                        username      TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role          TEXT NOT NULL DEFAULT 'reader',
                        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS can_edit_floor_plan BOOLEAN DEFAULT FALSE;")
                for username, role in [("admin", "admin"), ("writer", "writer"), ("reader", "reader")]:
                    pwd_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode()
                    cur.execute(
                        "INSERT INTO app_users (username,password_hash,role) VALUES (%s,%s,%s) "
                        "ON CONFLICT (username) DO NOTHING",
                        (username, pwd_hash, role),
                    )
    except Exception as exc:
        logger.warning("[HostAI] - Auth: ensure_default_users failed (non-fatal): %s", exc)


def _create_user(username: str, password: str, role: str) -> dict:
    pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_users (username, password_hash, role) VALUES (%s,%s,%s) "
                "ON CONFLICT (username) DO UPDATE SET password_hash=EXCLUDED.password_hash,role=EXCLUDED.role "
                "RETURNING id,username,role",
                (username, pwd_hash, role),
            )
            row = cur.fetchone()
        return dict(row)


# ─── JWT helpers ─────────────────────────────────────────────────────────────

def _create_token(username: str, role: str, can_edit_floor_plan: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    payload = {"sub": username, "role": role, "can_edit_floor_plan": can_edit_floor_plan, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Auth dependency ──────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    payload = _decode_token(token)
    return UserInfo(
        username=payload["sub"],
        role=payload["role"],
        can_edit_floor_plan=payload.get("can_edit_floor_plan", False),
    )


def require_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_writer(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if user.role not in ("admin", "writer"):
        raise HTTPException(status_code=403, detail="Writer or admin role required")
    return user


# ─── Auth router ──────────────────────────────────────────────────────────────

from fastapi import APIRouter

auth_router = APIRouter()


@auth_router.post("/token", response_model=Token, tags=["Auth"])
async def login(form: OAuth2PasswordRequestForm = Depends()) -> Token:
    """Authenticate with username/password. Returns JWT bearer token."""
    user = _get_user(form.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(form.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_token(user["username"], user["role"], bool(user.get("can_edit_floor_plan", False)))
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=user["role"],
    )


@auth_router.get("/me", response_model=UserInfo, tags=["Auth"])
async def me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    return user


@auth_router.get("/users", tags=["Auth"])
async def list_users(admin: UserInfo = Depends(require_admin)) -> dict:
    """Admin only: list all users."""
    users = _list_users()
    return {"users": [{"id": u["id"], "username": u["username"], "role": u["role"], "can_edit_floor_plan": u["can_edit_floor_plan"]} for u in users]}


@auth_router.post("/users", tags=["Auth"])
async def create_user(
    body: CreateUserRequest,
    admin: UserInfo = Depends(require_admin),
) -> dict:
    """Admin only: create or update a user."""
    username = body.username.strip()
    password = body.password.strip()
    role = body.role
    if not username or not password:
        raise HTTPException(status_code=422, detail="username and password required")
    if role not in ("admin", "writer", "reader"):
        raise HTTPException(status_code=422, detail="role must be admin|writer|reader")
    user = _create_user(username, password, role)
    return {"message": f"User '{username}' created/updated", "user": user}


@auth_router.patch("/users/{username}/permissions", tags=["Auth"])
async def update_user_permissions(
    username: str,
    body: UpdatePermissionsRequest,
    admin: UserInfo = Depends(require_admin),
) -> dict:
    """Admin only: update user permissions (e.g. can_edit_floor_plan)."""
    can_edit = body.can_edit_floor_plan
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_users SET can_edit_floor_plan=%s WHERE username=%s RETURNING id,username,role,can_edit_floor_plan",
                    (bool(can_edit), username),
                )
                row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"User '{username}' not found")
            return {"message": f"Permissions updated for '{username}'", "user": dict(row)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
