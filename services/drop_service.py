import random
import discord
from discord.ext import tasks
from database.currency import add_balance
from database.drop_log import log_drop
from config.constants import DROP_ANNOUNCE_CHANNEL_ID

class DropService:
    def __init__(self):
        self._bot = None
        self._enabled = False
        self._first_run = True                   # 启动后首次跳过掉落
        self.drop_rate_percent = 10              # 抽奖比例，默认10%
        self.drop_amount = 5                     # 每人掉落晶核数量
        self.drop_interval_minutes = 30          # 掉落周期（分钟）

    def start(self, bot):
        self._bot = bot
        self._enabled = True
        self._drop_loop.change_interval(minutes=self.drop_interval_minutes)
        self._drop_loop.start()

    def stop(self):
        self._enabled = False
        self._drop_loop.cancel()

    def is_active(self):
        return self._enabled

    @tasks.loop(minutes=30)
    async def _drop_loop(self):
        if self._first_run:
            print("[跳过] 启动时首次掉落被忽略")
            self._first_run = False
            return

        all_eligible = []

        for guild in self._bot.guilds:
            for vc in guild.voice_channels:
                members = [m for m in vc.members if not m.bot and not m.voice.deaf]
                if members:
                    print(f"[收集] {guild.name} - {vc.name}：{len(members)} 名 eligible 成员")
                all_eligible.extend(members)

        total_count = len(all_eligible)
        print(f"[掉落统计] 全服 eligible 总人数：{total_count}")

        if total_count == 0:
            print("[跳过] 本轮无人 eligible，未发放奖励")
            return

        pick_count = max(1, (total_count * self.drop_rate_percent) // 100)
        chosen = random.sample(all_eligible, pick_count)

        print(f"[抽奖] 抽取比例 {self.drop_rate_percent}%，目标人数：{pick_count}")
        for user in chosen:
            print(f"💎 发放对象：{user.name}（ID: {user.id}），数量：{self.drop_amount}")
            add_balance(user.id, self.drop_amount)
            log_drop(user.id, self.drop_amount)

            try:
                voice_channel = user.voice.channel
                await voice_channel.send(
                    embed=discord.Embed(
                        description=f"🎁 {user.display_name} 获得了 {self.drop_amount} 枚遗迹晶核！",
                        color=discord.Color.gold()
                    )
                )
            except:
                pass

        try:
            channel = self._bot.get_channel(DROP_ANNOUNCE_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="📢 本次掉落奖励已发放！",
                    description="\n".join(
                        f"🎉 {user.display_name} 获得 {self.drop_amount} 枚晶核"
                        for user in chosen
                    ),
                    color=discord.Color.teal()
                )
                await channel.send(embed=embed)
        except Exception as e:
            print(f"[错误] 广播失败：{e}")

    @_drop_loop.before_loop
    async def _before_drop(self):
        await self._bot.wait_until_ready()
