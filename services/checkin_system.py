# === checkin_system.py ===
from datetime import datetime, timedelta, timezone
from database.checkin_database import (
    init_checkin_db,
    get_checkin_data,
    update_checkin_data,
    insert_checkin_data,
    get_streak,
    get_max_streak
)

class CheckinSystem:
    def __init__(self):
        init_checkin_db()

    def has_checked_in_today(self, user_id: str) -> bool:
        row = get_checkin_data(user_id)
        if not row:
            return False

        try:
            last_checkin = datetime.fromisoformat(row[0])
        except Exception:
            return False

        now = datetime.now(timezone.utc)
        return last_checkin.date() == now.date()

    def record_checkin(self, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        row = get_checkin_data(user_id)

        if row:
            try:
                last_checkin = datetime.fromisoformat(row[0])
            except Exception:
                last_checkin = now - timedelta(days=2)

            streak = row[1]
            max_streak = row[2] if len(row) > 2 else streak

            if (now.date() - last_checkin.date()).days == 1:
                streak += 1
            else:
                streak = 1

            max_streak = max(max_streak, streak)
            update_checkin_data(user_id, now.isoformat(), streak, max_streak)
        else:
            insert_checkin_data(user_id, now.isoformat())
            streak = 1

        return streak

    def get_streak(self, user_id: str) -> int:
        return get_streak(user_id)

    def get_max_streak(self, user_id: str) -> int:
        return get_max_streak(user_id)

    async def grant_rewards(self, user_id: str):
        try:
            from database.currency import add_balance
            from database.dao_user import update_user
            from services.xp_tracker import get_or_create_user, apply_xp_and_check_level

            user = get_or_create_user(user_id)

            for xp_type, amount in [("text", 50), ("voice", 100), ("stream", 200)]:
                _, user = await apply_xp_and_check_level(user, xp_type, amount)

            update_user(user)
            add_balance(user_id, 0)

        except ImportError as e:
            print(f"⚠ 模块导入失败：{e.__class__.__name__}: {e}")

    async def sign_in(self, user_id: str) -> tuple[bool, int]:
        if self.has_checked_in_today(user_id):
            return False, self.get_streak(user_id)

        streak = self.record_checkin(user_id)
        await self.grant_rewards(user_id)

        try:
            from services.mengmeng_service import grant_checkin_reward_if_eligible
            grant_checkin_reward_if_eligible(user_id, streak)
        except Exception:
            pass

        return True, streak

    def get_leaderboard(self, limit=10):
        from database.checkin_database import get_top_checkins
        return get_top_checkins(limit)

    def get_max_streak_leaderboard(self, limit=10):
        from database.checkin_database import get_top_max_checkins
        return get_top_max_checkins(limit)

    def get_user_rank(self, user_id: str) -> int:
        from database.checkin_database import get_user_checkin_rank
        return get_user_checkin_rank(user_id)
