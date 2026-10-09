import json
import sqlite3
from datetime import datetime, timezone


DB_PATH = "avalon.db"
ACTIVE_STATUSES = (
    "LOBBY",
    "ROLE_CONFIRMATION",
    "TEAM_PROPOSAL",
    "TEAM_VOTE",
    "TEAM_VOTE_RESULT",
    "QUEST_SUBMISSION",
    "QUEST_RESULT",
    "ASSASSINATION",
)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_avalon_tables():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS avalon_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT,
                owner_id TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_avalon_channel_status "
            "ON avalon_games(channel_id, status)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS avalon_results (
                game_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                side TEXT NOT NULL,
                won INTEGER NOT NULL,
                win_code TEXT,
                played_at TEXT NOT NULL,
                PRIMARY KEY (game_id, user_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_avalon_results_user "
            "ON avalon_results(user_id)"
        )


def create_game(state: dict) -> dict:
    init_avalon_tables()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO avalon_games (
                guild_id, channel_id, message_id, owner_id, status,
                state_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(state["guild_id"]),
                str(state["channel_id"]),
                str(state.get("message_id") or ""),
                str(state["owner_id"]),
                state["status"],
                json.dumps(state, ensure_ascii=False),
                now,
                now,
            ),
        )
        state = dict(state)
        state["id"] = int(cursor.lastrowid)
        conn.execute(
            "UPDATE avalon_games SET state_json = ? WHERE id = ?",
            (json.dumps(state, ensure_ascii=False), state["id"]),
        )
        return state


def save_game(state: dict):
    init_avalon_tables()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE avalon_games
            SET message_id = ?, status = ?, state_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(state.get("message_id") or ""),
                state["status"],
                json.dumps(state, ensure_ascii=False),
                now,
                int(state["id"]),
            ),
        )


def _decode(row) -> dict | None:
    if not row:
        return None
    state = json.loads(row["state_json"])
    state["id"] = int(row["id"])
    return state


def get_game(game_id: int) -> dict | None:
    init_avalon_tables()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, state_json FROM avalon_games WHERE id = ?",
            (int(game_id),),
        ).fetchone()
        return _decode(row)


def get_game_by_message(message_id: int | str) -> dict | None:
    init_avalon_tables()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, state_json FROM avalon_games
            WHERE message_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (str(message_id),),
        ).fetchone()
        return _decode(row)


def get_active_game_for_channel(channel_id: int | str) -> dict | None:
    init_avalon_tables()
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT id, state_json FROM avalon_games
            WHERE channel_id = ? AND status IN ({placeholders})
            ORDER BY id DESC LIMIT 1
            """,
            (str(channel_id), *ACTIVE_STATUSES),
        ).fetchone()
        return _decode(row)


def list_active_games() -> list[dict]:
    init_avalon_tables()
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, state_json FROM avalon_games
            WHERE status IN ({placeholders}) AND message_id != ''
            ORDER BY id
            """,
            ACTIVE_STATUSES,
        ).fetchall()
        return [_decode(row) for row in rows]


def record_game_results(state: dict) -> int:
    """Persist one finished game's player results exactly once."""
    if state.get("status") != "FINISHED" or not state.get("winner"):
        return 0
    init_avalon_tables()
    played_at = state.get("finished_at") or datetime.now(timezone.utc).isoformat()
    rows = []
    for player in state.get("players", []):
        user_id = str(player["id"])
        role = state["roles"][user_id]
        side = "GOOD" if role in {"MERLIN", "PERCIVAL", "LOYAL_SERVANT"} else "EVIL"
        rows.append(
            (
                int(state["id"]),
                user_id,
                role,
                side,
                int(side == state["winner"]),
                state.get("win_code"),
                played_at,
            )
        )
    with _connect() as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO avalon_results (
                game_id, user_id, role, side, won, win_code, played_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return conn.total_changes - before


def get_player_stats(user_id: int | str) -> dict:
    init_avalon_tables()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_games,
                COALESCE(SUM(won), 0) AS wins,
                COALESCE(SUM(
                    CASE WHEN role = 'MERLIN' AND won = 1
                              AND win_code = 'ASSASSIN_MISSED'
                         THEN 1 ELSE 0 END
                ), 0) AS merlin_survived_wins,
                COALESCE(SUM(
                    CASE WHEN role = 'ASSASSIN'
                              AND win_code = 'ASSASSIN_HIT'
                         THEN 1 ELSE 0 END
                ), 0) AS assassin_hits
            FROM avalon_results
            WHERE user_id = ?
            """,
            (str(user_id),),
        ).fetchone()
    total_games = int(row["total_games"])
    wins = int(row["wins"])
    return {
        "total_games": total_games,
        "wins": wins,
        "win_rate": (wins / total_games * 100.0) if total_games else 0.0,
        "merlin_survived_wins": int(row["merlin_survived_wins"]),
        "assassin_hits": int(row["assassin_hits"]),
    }


def get_leaderboard(metric: str = "wins", limit: int = 10) -> list[dict]:
    order_by = {
        "wins": "wins DESC, win_rate DESC, total_games DESC, user_id ASC",
        "win_rate": "win_rate DESC, wins DESC, total_games DESC, user_id ASC",
        "games": "total_games DESC, wins DESC, win_rate DESC, user_id ASC",
    }
    if metric not in order_by:
        raise ValueError(f"unsupported leaderboard metric: {metric}")
    init_avalon_tables()
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                user_id,
                COUNT(*) AS total_games,
                SUM(won) AS wins,
                100.0 * SUM(won) / COUNT(*) AS win_rate,
                SUM(CASE WHEN role = 'MERLIN' AND won = 1
                              AND win_code = 'ASSASSIN_MISSED'
                         THEN 1 ELSE 0 END) AS merlin_survived_wins,
                SUM(CASE WHEN role = 'ASSASSIN'
                              AND win_code = 'ASSASSIN_HIT'
                         THEN 1 ELSE 0 END) AS assassin_hits
            FROM avalon_results
            GROUP BY user_id
            HAVING COUNT(*) >= 3
            ORDER BY {order_by[metric]}
            LIMIT ?
            """,
            (max(1, min(int(limit), 25)),),
        ).fetchall()
    return [
        {
            "user_id": row["user_id"],
            "total_games": int(row["total_games"]),
            "wins": int(row["wins"]),
            "win_rate": float(row["win_rate"]),
            "merlin_survived_wins": int(row["merlin_survived_wins"]),
            "assassin_hits": int(row["assassin_hits"]),
        }
        for row in rows
    ]
