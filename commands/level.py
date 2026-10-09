import discord
from discord.ext import commands
from database.dao_user import get_or_create_user, modify_user_xp, get_all_users
from services.xp_tracker import get_level_from_xp, get_required_xp
from config.level_roles import LEVEL_ROLE_MAP
from services.role_utils import check_level_change

def setup(bot):
    ALLOWED_ROLE_IDS = {0}

    # 查看等级指令
    @bot.command(name="rank")
    async def level(ctx, target: discord.Member = None):
        if target and target != ctx.author:
            has_allowed_role = any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)
            if not has_allowed_role and not ctx.author.guild_permissions.administrator:
                return await ctx.send("❌ 你没有权限查看他人的等级信息。")

        member = target or ctx.author
        user = get_or_create_user(str(member.id))

        text_level = get_level_from_xp("text", user.text_xp)
        voice_level = get_level_from_xp("voice", user.voice_xp)
        stream_level = get_level_from_xp("stream", user.stream_xp)

        next_text = get_required_xp("text", text_level + 1)
        next_voice = get_required_xp("voice", voice_level + 1)
        next_stream = get_required_xp("stream", stream_level + 1)

        def fmt_line(icon, label, lv, cur, maxv):
            label_part = f"{icon}{label:<8} Lv.{lv:<8}({cur:>5}/{maxv:<5})"
            return f"{label_part:<40}"

        total_level = text_level + voice_level + stream_level
        role_name = None
        for lvl, name, _ in LEVEL_ROLE_MAP:
            if total_level >= lvl:
                role_name = name

        description = (
            f"\U0001f3db 遗迹等级 ： Lv.{total_level}\n"
            f"{fmt_line('\U0001f4e8', '文字等级 ：', text_level, user.text_xp, next_text)}\n"
            f"{fmt_line('\U0001f3a7', '语音等级 ：', voice_level, user.voice_xp, next_voice)}\n"
            f"{fmt_line('\U0001f4f9', '直播等级 ：', stream_level, user.stream_xp, next_stream)}\n"
            f"\U0001f451 当前称号 ： {role_name or '无'}"
        )

        embed = discord.Embed(
            title=f"🏅 {member.display_name} 的等级信息",
            description=description,
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        await ctx.send(embed=embed)

        try:
            await check_level_change(member, user)
        except Exception as e:
            print(f"⚠️ 更新 {member.display_name} 的身份组失败：{e}")

    # 管理员：增加经验指令
    @bot.command(name="exp")
    @commands.has_permissions(administrator=True)
    async def give_exp(ctx, member: discord.Member, xp_type: str, amount: int):
        if xp_type not in ("text", "voice", "stream"):
            await ctx.send("❌ 类型必须是 text / voice / stream")
            return

        user_id = str(member.id)
        modify_user_xp(user_id, xp_type, amount)

        # 经验修改后刷新身份组
        user = get_or_create_user(user_id)
        await check_level_change(member, user)

        await ctx.send(f"✅ 已增加 {member.mention} 的 {xp_type} 经验：{amount}")

    # 管理员：减少经验指令
    @bot.command(name="dexp")
    @commands.has_permissions(administrator=True)
    async def reduce_exp(ctx, member: discord.Member, xp_type: str, amount: int):
        if xp_type not in ("text", "voice", "stream"):
            await ctx.send("❌ 类型必须是 text / voice / stream")
            return

        user_id = str(member.id)
        modify_user_xp(user_id, xp_type, -amount)

        # 经验修改后刷新身份组
        user = get_or_create_user(user_id)
        await check_level_change(member, user)

        await ctx.send(f"✅ 已减少 {member.mention} 的 {xp_type} 经验：{amount}")

    # === 管理员：查看等级排行榜（带@mention版） ===
    @bot.command(name="ranrank")
    @commands.has_permissions(administrator=True)
    async def view_leaderboard(ctx, top_n: int = 10):
        users = get_all_users()

        leaderboard = []
        for user in users:
            text_level = get_level_from_xp("text", user.text_xp)
            voice_level = get_level_from_xp("voice", user.voice_xp)
            stream_level = get_level_from_xp("stream", user.stream_xp)
            total_level = text_level + voice_level + stream_level
            leaderboard.append((user.user_id, total_level))

        leaderboard.sort(key=lambda x: x[1], reverse=True)
        top_n = min(top_n, 50)  # 限制最大50名
        top_users = leaderboard[:top_n]

        if not top_users:
            await ctx.send("📋 当前没有任何等级数据。")
            return

        embed = discord.Embed(
            title=f"🏆 等级排行榜 (前{top_n}名)",
            color=discord.Color.gold()
        )

        description = ""
        for i, (user_id, total_level) in enumerate(top_users, start=1):
            try:
                user = await bot.fetch_user(int(user_id))
                name = user.mention  # <<< 改成mention可跳转
            except Exception:
                name = f"用户ID:{user_id}"
            description += f"`{i:02d}` {name} - 总等级 {total_level}\n"

        embed.description = description
        await ctx.send(embed=embed)

    # === 管理员：查看等级分布 ===
    @bot.command(name="sprank")
    @commands.has_permissions(administrator=True)
    async def view_level_distribution(ctx):
        users = get_all_users()

        distribution = {}
        for user in users:
            text_level = get_level_from_xp("text", user.text_xp)
            voice_level = get_level_from_xp("voice", user.voice_xp)
            stream_level = get_level_from_xp("stream", user.stream_xp)
            total_level = text_level + voice_level + stream_level

            if total_level >= 7:
                key = "7+"
            elif total_level >= 5:
                key = "5-6"
            elif total_level >= 3:
                key = "3-4"
            elif total_level >= 1:
                key = "1-2"
            else:
                key = "0-1"

            distribution[key] = distribution.get(key, 0) + 1

        if not distribution:
            await ctx.send("📋 当前没有任何等级数据。")
            return

        embed = discord.Embed(
            title="📊 等级分布统计",
            color=discord.Color.blue()
        )

        ranges = ["0-1", "1-2", "3-4", "5-6", "7+"]
        for r in ranges:
            count = distribution.get(r, 0)
            embed.add_field(name=f"等级{r}", value=f"{count}人", inline=False)

        await ctx.send(embed=embed)

    # === 管理员：查看指定玩家最后活跃日期 ===
    @bot.command(name="lastlive")
    @commands.has_permissions(administrator=True)
    async def view_last_active(ctx, member: discord.Member):
        user = get_or_create_user(str(member.id))
        last_active = user.last_active_date

        embed = discord.Embed(
            title=f"📅 {member.display_name} 的最后活跃日期",
            color=discord.Color.teal()
        )

        if not last_active:
            embed.description = "无记录。"
        else:
            embed.description = f"{last_active}"

        await ctx.send(embed=embed)

    # === 管理员：查看指定玩家未活跃天数 ===
    @bot.command(name="inactive")
    @commands.has_permissions(administrator=True)
    async def view_inactive_days(ctx, member: discord.Member):
        from datetime import datetime, timezone

        user = get_or_create_user(str(member.id))
        today = datetime.now(timezone.utc).date()

        embed = discord.Embed(
            title=f"⏳ {member.display_name} 的未活跃天数",
            color=discord.Color.purple()
        )

        if not user.last_active_date:
            embed.description = "无记录。"
            await ctx.send(embed=embed)
            return

        try:
            last_active = datetime.strptime(user.last_active_date, "%Y-%m-%d").date()
        except Exception:
            embed.description = f"⚠️ 日期格式错误：{user.last_active_date}"
            await ctx.send(embed=embed)
            return

        inactive_days = (today - last_active).days
        inactive_days = max(0, inactive_days)

        embed.description = f"{inactive_days} 天"
        await ctx.send(embed=embed)
