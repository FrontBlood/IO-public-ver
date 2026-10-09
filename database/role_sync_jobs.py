import json
import sqlite3
from datetime import datetime, timezone

from config.constants import DB_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_role_sync_job_table():
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS role_sync_jobs (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                target_role_id TEXT,
                roles_to_remove TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reason TEXT NOT NULL DEFAULT 'level_sync',
                last_error TEXT NOT NULL DEFAULT '',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        conn.commit()


def upsert_role_sync_job(
    guild_id: str,
    user_id: str,
    target_role_id: int | None,
    roles_to_remove: list[int],
    status: str = "pending",
    reason: str = "level_sync",
    last_error: str = "",
):
    now = _now_iso()
    payload = json.dumps(sorted(set(roles_to_remove)))
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO role_sync_jobs (
                guild_id, user_id, target_role_id, roles_to_remove, status,
                reason, last_error, attempt_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                target_role_id = excluded.target_role_id,
                roles_to_remove = excluded.roles_to_remove,
                status = excluded.status,
                reason = excluded.reason,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                guild_id,
                user_id,
                str(target_role_id) if target_role_id is not None else None,
                payload,
                status,
                reason,
                last_error,
                now,
                now,
            ),
        )
        conn.commit()


def get_role_sync_job(guild_id: str, user_id: str):
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT guild_id, user_id, target_role_id, roles_to_remove, status,
                   reason, last_error, attempt_count, created_at, updated_at
            FROM role_sync_jobs
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        row = c.fetchone()

    if not row:
        return None

    return {
        "guild_id": row[0],
        "user_id": row[1],
        "target_role_id": int(row[2]) if row[2] else None,
        "roles_to_remove": json.loads(row[3]),
        "status": row[4],
        "reason": row[5],
        "last_error": row[6],
        "attempt_count": row[7],
        "created_at": row[8],
        "updated_at": row[9],
    }


def update_role_sync_job_status(
    guild_id: str,
    user_id: str,
    status: str,
    *,
    last_error: str | None = None,
    increment_attempt: bool = False,
):
    now = _now_iso()
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        if increment_attempt:
            c.execute(
                """
                UPDATE role_sync_jobs
                SET status = ?, last_error = COALESCE(?, last_error),
                    attempt_count = attempt_count + 1, updated_at = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (status, last_error, now, guild_id, user_id),
            )
        else:
            c.execute(
                """
                UPDATE role_sync_jobs
                SET status = ?, last_error = COALESCE(?, last_error), updated_at = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (status, last_error, now, guild_id, user_id),
            )
        conn.commit()


def delete_role_sync_job(guild_id: str, user_id: str):
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM role_sync_jobs WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        conn.commit()


def get_incomplete_role_sync_jobs(limit: int = 100):
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT guild_id, user_id, target_role_id, roles_to_remove, status,
                   reason, last_error, attempt_count, created_at, updated_at
            FROM role_sync_jobs
            WHERE status != 'completed'
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = c.fetchall()

    jobs = []
    for row in rows:
        jobs.append(
            {
                "guild_id": row[0],
                "user_id": row[1],
                "target_role_id": int(row[2]) if row[2] else None,
                "roles_to_remove": json.loads(row[3]),
                "status": row[4],
                "reason": row[5],
                "last_error": row[6],
                "attempt_count": row[7],
                "created_at": row[8],
                "updated_at": row[9],
            }
        )
    return jobs
