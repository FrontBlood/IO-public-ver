# services/temp_role_checker.py
from discord.ext import tasks
from datetime import datetime, timezone, time as dtime
from database.temp_roles import get_temp_roles_due, remove_temp_role_entry
from config.constants import TEMP_PATH
import asyncio

semaphore = asyncio.Semaphore(1)  # 限制并发执行的协程数
DELAY_BETWEEN_ACTIONS = 1.5       # 每次操作间隔（秒）

# 并发安全地移除角色
async def safe_remove_role(member, role):
    async with semaphore:
        try:
            await member.remove_roles(role, reason="自动删除过期标签")
        except Exception as e:
            print(f"[⚠] 无法移除 {member} 的角色 {role}：{e}")
        await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

# 启动递归检查进程
def start_temp_role_checker(bot):
    @tasks.loop(time=dtime(hour=0, minute=0, tzinfo=timezone.utc))  # 每天 UTC 0:00 执行
    async def check_temp_roles():
        now = datetime.now(timezone.utc)
        rows = get_temp_roles_due(now)

        for id_, guild_id, user_id, role_id, expire_at in rows:
            try:
                guild = bot.get_guild(int(guild_id))
                member = guild.get_member(int(user_id)) if guild else None
                role = guild.get_role(int(role_id)) if guild else None

                if member and role:
                    await safe_remove_role(member, role)

                remove_temp_role_entry(id_)
            except Exception:
                continue

    check_temp_roles.start()
