from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


DB_PATH = Path("data/agri_app.db")


@dataclass
class AuthUser:
    user_id: int
    username: str
    role: str
    token: str


class AppStorage:
    """SQLite-backed app persistence for auth, farmer profiles, and sync queue."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_users()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS farmer_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farmer_name TEXT NOT NULL,
                    county TEXT NOT NULL,
                    crop TEXT NOT NULL,
                    area_acres REAL NOT NULL,
                    budget_kes INTEGER NOT NULL,
                    phone TEXT,
                    owner_user_id INTEGER,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(owner_user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    processed_at TEXT
                );
                """
            )

    def _seed_users(self) -> None:
        existing = self.get_user_by_username("admin")
        if existing:
            return
        self.create_user("admin", "admin123", "admin")
        self.create_user("officer", "officer123", "officer")
        self.create_user("farmer", "farmer123", "farmer")

    def create_user(self, username: str, password: str, role: str) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        password_hash = self._hash_password(password)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, role, now),
            )
            return int(cur.lastrowid or 0)

    def get_user_by_username(self, username: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    def authenticate(self, username: str, password: str) -> AuthUser | None:
        row = self.get_user_by_username(username)
        if not row:
            return None
        if row["password_hash"] != self._hash_password(password):
            return None
        token = secrets.token_urlsafe(24)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, row["id"], now))
        return AuthUser(user_id=int(row["id"]), username=row["username"], role=row["role"], token=token)

    def user_from_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.username, u.role
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = ?
                """,
                (token,),
            ).fetchone()
        if not row:
            return None
        return {"id": int(row["id"]), "username": row["username"], "role": row["role"]}

    def save_farmer_profile(self, profile: dict[str, Any], owner_user_id: int | None = None) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            if profile.get("id"):
                conn.execute(
                    """
                    UPDATE farmer_profiles
                    SET farmer_name=?, county=?, crop=?, area_acres=?, budget_kes=?, phone=?, owner_user_id=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        profile["farmer_name"],
                        profile["county"],
                        profile["crop"],
                        float(profile["area_acres"]),
                        int(profile["budget_kes"]),
                        profile.get("phone"),
                        owner_user_id,
                        now,
                        int(profile["id"]),
                    ),
                )
                return int(profile["id"])
            cur = conn.execute(
                """
                INSERT INTO farmer_profiles
                (farmer_name, county, crop, area_acres, budget_kes, phone, owner_user_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile["farmer_name"],
                    profile["county"],
                    profile["crop"],
                    float(profile["area_acres"]),
                    int(profile["budget_kes"]),
                    profile.get("phone"),
                    owner_user_id,
                    now,
                ),
            )
            return int(cur.lastrowid or 0)

    def list_farmer_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM farmer_profiles ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_farmer_profile(self, profile_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM farmer_profiles WHERE id=?", (profile_id,)).fetchone()
        return dict(row) if row else None

    def enqueue_sync(self, action: str, payload: dict[str, Any]) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sync_queue (action, payload, status, attempts, created_at) VALUES (?, ?, 'pending', 0, ?)",
                (action, json.dumps(payload), now),
            )
            return int(cur.lastrowid or 0)

    def list_pending_sync(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sync_queue WHERE status='pending' ORDER BY id ASC").fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            out.append(item)
        return out

    def flush_sync_queue(self, max_items: int = 100) -> dict[str, int]:
        pending = self.list_pending_sync()[:max_items]
        if not pending:
            return {"processed": 0, "remaining": 0}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            for item in pending:
                conn.execute(
                    "UPDATE sync_queue SET status='done', attempts=attempts+1, processed_at=? WHERE id=?",
                    (now, int(item["id"])),
                )
        remaining = len(self.list_pending_sync())
        return {"processed": len(pending), "remaining": remaining}

    @staticmethod
    def _hash_password(password: str) -> str:
        return sha256(password.encode("utf-8")).hexdigest()
