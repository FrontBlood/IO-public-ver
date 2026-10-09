import asyncio
from datetime import datetime, time, timedelta, timezone

import discord

from config.constants import (
    CHECKIN_DB_PATH,
    CHECKIN_EVENT_ADMIN_USER_ID,
    CHECKIN_EVENT_CHANNEL_ID,
    CHECKIN_EVENT_DM_DELAY_SECONDS,
    CHECKIN_EVENT_DURATION_DAYS,
    CHECKIN_EVENT_REDEEM_CHANNEL_ID,
    CHECKIN_EVENT_REQUIRED_STREAK,
    CHECKIN_EVENT_REWARD_ROLE_ID,
    CHECKIN_EVENT_REWARD_LIMIT,
)
from database import checkin_event_database as event_db


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PUBLIC_EVENT_TITLE = "小月卡签到活动"


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def next_utc_refresh_plus_one_hour(base: datetime | None = None) -> datetime:
    base = (base or now_utc()).astimezone(timezone.utc)
    next_midnight = datetime.combine(base.date() + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return next_midnight + timedelta(hours=1)


def parse_event_end_date(raw: str) -> datetime:
    value = raw.strip()
    if len(value) == 10:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc) + timedelta(hours=1)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def generate_code(user_id: str, achieved_at: datetime, attempt: int = 0) -> str:
    date_digits = achieved_at.strftime("%Y%m%d%H%M%S")
    user_digits = user_id[-4:].zfill(4)
    digits = date_digits + user_digits + str(attempt)
    chars = []
    for i in range(8):
        a = int(digits[(i * 2) % len(digits)])
        b = int(digits[(i * 2 + 7) % len(digits)])
        c = int(digits[(i + 14) % len(digits)])
        index = (a + b * 3 + c * 7 + i * 11 + attempt * 5) % len(CODE_ALPHABET)
        chars.append(CODE_ALPHABET[index])
    return "".join(chars)


def is_checkin_event_locked() -> bool:
    event_db.init_checkin_event_db()
    return event_db.get_current_event() is not None


def is_checkin_shop_item_locked() -> bool:
    return is_checkin_event_locked()


def list_eligible_existing_users(required_streak: int = CHECKIN_EVENT_REQUIRED_STREAK) -> list[tuple[str, int, str]]:
    import sqlite3

    with sqlite3.connect(CHECKIN_DB_PATH, timeout=5.0) as conn:
        return conn.execute(
            """
            SELECT user_id, streak, COALESCE(last_checkin, '') AS last_checkin
            FROM user_checkin
            WHERE streak >= ?
            ORDER BY streak DESC, last_checkin ASC, user_id ASC
            """,
            (required_streak,),
        ).fetchall()


class CheckinEventService:
    def __init__(self):
        event_db.init_checkin_event_db()

    def current_event(self):
        return event_db.get_current_event()

    async def extend_latest_normal_event(self, bot: discord.Client, end_at: datetime) -> tuple[bool, str]:
        event = event_db.get_latest_normal_event()
        if not event:
            return False, "没有找到可延期的正式签到活动。"
        if end_at <= now_utc():
            return False, "新的结束时间必须晚于当前时间。"
        if end_at <= parse_dt(event["end_at"]):
            return False, "新的结束时间必须晚于当前活动结束时间。"

        status = "active" if now_utc() >= parse_dt(event["start_at"]) else "scheduled"
        event_db.update_event_end(int(event["id"]), end_at.isoformat(), status=status)
        event = event_db.get_event(int(event["id"]))
        await self.update_public_message(bot, event)
        self.queue_code_delivery(bot, int(event["id"]))
        return True, (
            f"签到活动已延期至 {end_at.strftime('%Y-%m-%d %H:%M:%S')} UTC，"
            f"状态已恢复为 `{status}`，已有获奖与兑奖记录已续传保留。"
        )

    def event_accepts_new_rewards(self, event) -> bool:
        if not event or event["status"] != "active":
            return False
        current = now_utc()
        return parse_dt(event["start_at"]) <= current < parse_dt(event["end_at"])

    def event_allows_activity_role(self, event) -> bool:
        if not event or event["status"] not in {"scheduled", "active"}:
            return False
        return now_utc() < parse_dt(event["end_at"])

    def remaining_slots(self, event) -> int:
        return max(0, int(event["reward_limit"]) - event_db.count_rewards(int(event["id"])))

    async def grant_reward_role(self, bot: discord.Client, user_id: str):
        for guild in bot.guilds:
            member = guild.get_member(int(user_id))
            if not member:
                continue
            role = guild.get_role(CHECKIN_EVENT_REWARD_ROLE_ID)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="checkin_event_reward_awarded")
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(
                        "[CheckinEvent] reward role grant failed: "
                        f"user={user_id} role={CHECKIN_EVENT_REWARD_ROLE_ID} error={type(exc).__name__}: {exc}"
                    )
            return

    async def grant_current_event_role(self, bot: discord.Client, user_id: str):
        event = self.current_event()
        if self.event_allows_activity_role(event):
            await self.grant_reward_role(bot, user_id)

    def build_public_embed(self, event) -> discord.Embed:
        remaining = self.remaining_slots(event)
        embed = discord.Embed(
            title=PUBLIC_EVENT_TITLE,
            description=f"剩余奖励名额：**{remaining}** / {event['reward_limit']}",
            color=0x00CC99,
        )
        return embed

    async def update_public_message(self, bot: discord.Client, event=None):
        event = event or self.current_event()
        if not event:
            return
        event = event_db.get_event(int(event["id"])) or event
        channel = bot.get_channel(int(event["announce_channel_id"]))
        if channel is None:
            channel = await bot.fetch_channel(int(event["announce_channel_id"]))
        embed = self.build_public_embed(event)
        message_id = event["announce_message_id"]
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=embed)
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        async for message in channel.history(limit=50):
            if message.author.id != bot.user.id:
                continue
            if any(embed.title in {PUBLIC_EVENT_TITLE, "原神牛逼签到活动"} for embed in message.embeds):
                await message.edit(embed=embed)
                event_db.update_announce_message(int(event["id"]), str(message.id))
                return
        message = await channel.send(embed=embed)
        event_db.update_announce_message(int(event["id"]), str(message.id))

    async def create_event(self, bot: discord.Client, created_by: str) -> tuple[bool, str]:
        if self.current_event():
            return False, "当前已有签到活动处于等待开始或进行中。"

        eligible = list_eligible_existing_users()
        if len(eligible) > CHECKIN_EVENT_REWARD_LIMIT:
            return False, f"当前已满足条件的人数为 {len(eligible)}，超过 {CHECKIN_EVENT_REWARD_LIMIT} 个名额，活动未开启。"

        start_at = next_utc_refresh_plus_one_hour()
        end_at = start_at + timedelta(days=CHECKIN_EVENT_DURATION_DAYS)
        event = event_db.create_event(
            created_by=created_by,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            reward_limit=CHECKIN_EVENT_REWARD_LIMIT,
            required_streak=CHECKIN_EVENT_REQUIRED_STREAK,
            announce_channel_id=str(CHECKIN_EVENT_CHANNEL_ID),
            redeem_channel_id=str(CHECKIN_EVENT_REDEEM_CHANNEL_ID),
            admin_user_id=str(CHECKIN_EVENT_ADMIN_USER_ID),
            mode="normal",
        )
        await self.update_public_message(bot, event)
        event = self.current_event()
        await self.sync_existing_eligible_rewards(bot, event, allow_scheduled=True)
        self.queue_code_delivery(bot, int(event["id"]))
        return True, (
            "签到活动已开启。旧签到入口与时空传送已即时停用，"
            f"活动计时从 {start_at.strftime('%Y-%m-%d %H:%M:%S')} UTC 开始。"
        )

    async def sync_existing_eligible_rewards(self, bot: discord.Client, event, *, allow_scheduled: bool = False):
        if not event:
            return
        for user_id, streak, _last_checkin in list_eligible_existing_users(int(event["required_streak"])):
            await self.grant_reward(bot, event, str(user_id), int(streak), allow_scheduled=allow_scheduled)
        self.queue_code_delivery(bot, int(event["id"]))
        await self.update_public_message(bot, event)

    async def create_test_event(self, bot: discord.Client, admin_user_id: str) -> tuple[bool, str]:
        if self.current_event():
            return False, "当前已有签到活动处于等待开始或进行中，请先关闭测试或等待正式活动结束。"

        start_at = now_utc()
        end_at = start_at + timedelta(hours=6)
        event = event_db.create_event(
            created_by=admin_user_id,
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            reward_limit=1,
            required_streak=1,
            announce_channel_id=str(CHECKIN_EVENT_CHANNEL_ID),
            redeem_channel_id=str(CHECKIN_EVENT_REDEEM_CHANNEL_ID),
            admin_user_id=str(admin_user_id),
            mode="test",
        )
        event_db.update_event_status(int(event["id"]), "active")
        event = self.current_event()
        await self.update_public_message(bot, event)
        event = self.current_event()
        await self.grant_reward(bot, event, admin_user_id, 1)
        self.queue_code_delivery(bot, int(event["id"]))
        return True, "测试签到活动已开启，测试兑换码将私信发送给你。"

    async def close_test_event(self, bot: discord.Client, admin_user_id: str) -> tuple[bool, str]:
        event = self.current_event()
        if not event or event["mode"] != "test":
            return False, "当前没有测试签到活动。"
        if str(event["admin_user_id"]) != str(admin_user_id):
            return False, "只有开启测试活动的管理员可以关闭这个测试。"
        if event["announce_message_id"]:
            try:
                channel = bot.get_channel(int(event["announce_channel_id"])) or await bot.fetch_channel(
                    int(event["announce_channel_id"])
                )
                message = await channel.fetch_message(int(event["announce_message_id"]))
                await message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            channel = bot.get_channel(int(event["announce_channel_id"])) or await bot.fetch_channel(
                int(event["announce_channel_id"])
            )
            async for message in channel.history(limit=50):
                if message.author.id == bot.user.id and any(
                    embed.title in {PUBLIC_EVENT_TITLE, "原神牛逼签到活动"} for embed in message.embeds
                ):
                    await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        event_db.delete_event(int(event["id"]))
        return True, "测试签到活动已关闭，测试活动记录已清理。"

    async def refresh_status(self, bot: discord.Client):
        event = self.current_event()
        if not event:
            return
        current = now_utc()
        event_id = int(event["id"])
        if current >= parse_dt(event["end_at"]):
            event_db.update_event_status(event_id, "ended")
            await self.update_public_message(bot, event)
            return
        if event["status"] == "scheduled" and current >= parse_dt(event["start_at"]):
            event_db.update_event_status(event_id, "active")
            event = self.current_event()
            await self.sync_existing_eligible_rewards(bot, event)

    async def handle_successful_checkin(self, bot: discord.Client, user_id: str, streak: int):
        await self.refresh_status(bot)
        event = self.current_event()
        if not self.event_accepts_new_rewards(event):
            return
        await self.grant_reward(bot, event, user_id, streak)
        self.queue_code_delivery(bot, int(event["id"]))

    async def grant_reward(
        self,
        bot: discord.Client,
        event,
        user_id: str,
        streak: int,
        *,
        allow_scheduled: bool = False,
    ):
        if streak < int(event["required_streak"]):
            return None
        if event_db.get_reward_by_user(int(event["id"]), user_id):
            return None
        if not allow_scheduled and not self.event_accepts_new_rewards(event):
            return None
        if self.remaining_slots(event) <= 0:
            return None

        achieved_at = now_utc()
        for attempt in range(50):
            code = generate_code(user_id, achieved_at, attempt)
            if not event_db.code_exists(code):
                reward = event_db.add_reward(int(event["id"]), user_id, achieved_at.isoformat(), code)
                if reward:
                    await self.update_public_message(bot, event)
                    return reward
        return None

    def queue_code_delivery(self, bot: discord.Client, event_id: int):
        task = getattr(bot, "_checkin_event_dm_task", None)
        if task and not task.done():
            return
        bot._checkin_event_dm_task = bot.loop.create_task(self.deliver_pending_codes(bot, event_id))

    async def deliver_pending_codes(self, bot: discord.Client, event_id: int):
        while True:
            pending = event_db.list_unsent_rewards(event_id)
            if not pending:
                return
            for reward in pending:
                try:
                    user = bot.get_user(int(reward["user_id"])) or await bot.fetch_user(int(reward["user_id"]))
                    await user.send(
                        f"【遗迹】小月卡签到活动 - 奖励兑换码：`{reward['code']}`"
                    )
                    event_db.mark_code_sent(int(reward["id"]))
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                    event_db.mark_code_send_error(int(reward["id"]), f"{exc.__class__.__name__}: {exc}")
                await asyncio.sleep(float(CHECKIN_EVENT_DM_DELAY_SECONDS))

    def verify_redeem(self, user_id: str, code: str):
        reward = event_db.get_reward_by_code(code)
        if not reward:
            return None, "没有找到这个兑奖码。"
        if str(reward["user_id"]) != str(user_id):
            return None, "这个兑奖码不属于你。"
        if reward["settled_at"]:
            return None, "这个兑奖码已经结算完成。"
        return reward, ""

    def mark_redeemed(
        self,
        reward,
        redeem_channel_id: str,
        redeem_message_id: str,
    ):
        event_db.mark_redeemed(int(reward["id"]), redeem_channel_id, redeem_message_id)

    def build_redeem_review_embed(self, reward) -> discord.Embed:
        return discord.Embed(
            title="小月卡签到活动兑奖请求",
            description=(
                f"用户：<@{reward['user_id']}> (`{reward['user_id']}`)\n"
                f"兑奖码：`{reward['code']}`\n"
                f"获得时间：{reward['achieved_at']}"
            ),
            color=0xFFCC00,
        )

    async def notify_admin_redeem_detail(self, bot: discord.Client, reward):
        event = event_db.get_event(int(reward["event_id"]))
        admin_user_id = int(event["admin_user_id"]) if event else CHECKIN_EVENT_ADMIN_USER_ID
        admin = bot.get_user(admin_user_id) or await bot.fetch_user(admin_user_id)
        await admin.send(embed=self.build_redeem_review_embed(reward))

    def record_settlement_message(self, reward_id: int, message_id: str):
        event_db.update_admin_message(reward_id, message_id)

    def settle_by_admin_message(self, message_id: str, admin_id: str) -> tuple[bool, str]:
        reward = event_db.get_reward_by_admin_message(message_id)
        if not reward:
            return False, "没有找到这条结算消息对应的兑奖记录。"
        event = event_db.get_event(int(reward["event_id"]))
        if event and str(event["admin_user_id"]) != str(admin_id):
            return False, "你没有权限结算这个兑奖请求。"
        if reward["settled_at"]:
            return False, "这条兑奖记录已经结算完成。"
        ok = event_db.mark_settled(int(reward["id"]), admin_id)
        if not ok:
            return False, "结算状态更新失败，可能已经被处理。"
        return True, f"结算完成：<@{reward['user_id']}> / `{reward['code']}`"


async def checkin_event_loop(bot: discord.Client, service: CheckinEventService):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await service.refresh_status(bot)
            event = service.current_event()
            if event:
                service.queue_code_delivery(bot, int(event["id"]))
                await service.update_public_message(bot, event)
        except Exception as exc:
            print(f"[CheckinEvent] loop failed: {exc}")
        await asyncio.sleep(300)
