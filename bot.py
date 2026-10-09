import discord
from discord.ext import tasks, commands
import os
import asyncio
import datetime
import sys
from dotenv import load_dotenv

load_dotenv()

from services.voice_stream_tasks import start_periodic_tasks, start_decay_loop
from services.database_backup import backup_project_databases
from core.events import register_events
from commands.level import setup as setup_level
# 导入货币相关
from database.currency import init_currency_db
from commands.currency_command import setup as setup_currency_commands
# 导入新人相关
from commands.newbee import setup as setup_newbee_commands
from services.temp_role_checker import start_temp_role_checker
from database.temp_roles import init_temp_role_table
# 导入签到相关
from commands.checkin import setup as setup_checkin_commands
from commands.checkin_event import setup as setup_checkin_event_commands
# 导入商店相关
from commands.shop_command import setup_shop_commands
from commands.help_center import setup as setup_help_center
from commands.private_room_maintenance import setup as setup_private_room_maintenance
from commands.level_role_maintenance import setup as setup_level_role_maintenance
from commands.message_management import setup as setup_message_management
from commands.spec import setup as setup_spec
from commands.system_admin import setup as setup_system_admin
from commands.user_activity_report import setup as setup_user_activity_report
from commands.tts import setup as setup_tts
from commands.omg import setup as setup_omg
from commands.tournament_template_maintenance import setup as setup_tournament_template_maintenance
from commands.avalon import setup as setup_avalon
# 导入掉落相关
from database.drop_log import init_drop_log
from commands.drop_command import setup as setup_drop_commands
# 导入成就相关
from database.achievement_dao import init_achievement_table
from commands import achievement_commands
# 导入擂台赛相关
from database.arena_dao import init_arena_table
from commands import arena_commands
from database.private_room_state import init_private_room_table
from database.role_sync_jobs import init_role_sync_job_table
from database.mvp_dao import init_mvp_tables
from database.checkin_event_database import init_checkin_event_db
from database.avalon_db import init_avalon_tables
from commands.mvp import setup as setup_mvp_commands
# 导入防诈相关

DECAY_HOUR = 4
DECAY_MINUTE = 50
RESTART_HOUR = 5
RESTART_MINUTE = 0

# 初始化
init_currency_db()
init_temp_role_table()
init_drop_log()
init_achievement_table()
init_arena_table()
init_private_room_table()
init_role_sync_job_table()
init_mvp_tables()
init_checkin_event_db()
init_avalon_tables()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="&", intents=intents, help_command=None)

# ✅ 注册指令模块
setup_level(bot)
# 注册货币指令
setup_currency_commands(bot)
setup_help_center(bot)
# 注册新人指令
setup_newbee_commands(bot)
# 注册签到指令
setup_checkin_commands(bot)
setup_checkin_event_commands(bot)
# 注册商店指令
setup_shop_commands(bot)
setup_private_room_maintenance(bot)
setup_level_role_maintenance(bot)
setup_message_management(bot)
setup_tournament_template_maintenance(bot)
setup_system_admin(bot)
setup_user_activity_report(bot)
setup_tts(bot)
setup_omg(bot)
setup_avalon(bot)
# 注册掉落指令
setup_drop_commands(bot)
# ✅ 注册事件模块（包含 on_ready 和 on_message）
register_events(bot, decay_hour=DECAY_HOUR, decay_minute=DECAY_MINUTE)
# 注册成就指令
achievement_commands.setup(bot)
# 注册擂台指令
arena_commands.setup(bot)
setup_spec(bot)
# 注册防诈指令


@bot.listen("on_ready")
async def _load_mvp_commands():
    try:
        if bot.get_cog("MVPCommands"):
            return
        await setup_mvp_commands(bot)
        print("[MVP] Commands loaded")
    except Exception as e:
        print(f"[MVP] failed to load commands: {e}")


async def daily_restart():
    """每天固定时间备份数据库并重启进程。"""
    await bot.wait_until_ready()
    print("⏳ 自动重启任务已启动（零循环模式）")

    while True:
        now = datetime.datetime.now()
        target = now.replace(
            hour=RESTART_HOUR,
            minute=RESTART_MINUTE,
            second=0,
            microsecond=0,
        )

        if target <= now:
            target += datetime.timedelta(days=1)

        wait_sec = (target - now).total_seconds()
        print(f"⏳ 距离下次自动重启还有 {wait_sec / 3600:.2f} 小时")
        await asyncio.sleep(wait_sec)

        print("🔄 正在自动重启 bot ……")
        try:
            backup_dir = backup_project_databases()
            print(f"[DatabaseBackup] Backup completed: {backup_dir}")
        except Exception as e:
            print(f"[DatabaseBackup] Backup failed, restart canceled: {e}")
            continue

        os.execv(sys.executable, [sys.executable] + sys.argv)


@bot.listen("on_ready")
async def _start_restart_timer():
    existing_task = getattr(bot, "_daily_restart_task", None)
    if existing_task and not existing_task.done():
        return

    bot._daily_restart_task = bot.loop.create_task(daily_restart())
    print("🕒 Auto-Restart Timer已启动（每日05:00）")


TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
