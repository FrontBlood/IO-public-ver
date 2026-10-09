from __future__ import annotations

import asyncio
from io import BytesIO

import discord
from discord.ext import commands

from services.omg_service import OmgInputError, process_omg_screenshot


MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
PROCESS_TIMEOUT_SECONDS = 90
_processing_slots = asyncio.Semaphore(2)
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def _find_image_attachment(ctx: commands.Context) -> discord.Attachment | None:
    for attachment in ctx.message.attachments:
        content_type = (attachment.content_type or "").lower()
        if content_type.startswith("image/") or attachment.filename.lower().endswith(_IMAGE_SUFFIXES):
            return attachment
    return None


def _format_result(
    recommendations: dict[str, tuple[str, ...]],
    combo_recommendations: dict[str, tuple[dict, ...]] | None = None,
) -> str:
    first = recommendations.get("first", ())
    second = recommendations.get("second", ())
    third = recommendations.get("third", ())
    lines = [
        f"第一推荐（T0/T1＋P0）：{'，'.join(first) if first else '无'}",
        f"第二推荐（T0/T1＋P1）：{'，'.join(second) if second else '无'}",
        f"第三推荐（T2以上＋P2以上）：{'，'.join(third) if third else '无'}",
    ]
    lines.append("标注说明：左上 T＝价值评级；右上 P＝抓位评级（P0 最早）")
    combos = combo_recommendations or {}
    pair_rows = combos.get("pairs", ())
    triplet_rows = combos.get("triplets", ())
    if pair_rows or triplet_rows:
        lines.append("高胜配组建议：")
        for label, rows in (("双技能", pair_rows), ("三技能", triplet_rows)):
            for row in rows:
                names = "＋".join(row["names"])
                lines.append(
                    f"{label}：{names}（胜率 {row['win_rate']:.1%}，"
                    f"协同 +{row['synergy']:.1%}，样本 {row['picks']:,}）"
                )
    elif combo_recommendations is not None:
        lines.append("高胜配组建议：当前画面无协同 ≥ 9.5%、胜率 ≥ 65% 的有效组合")
    lines.append("数据来源：Windrun API")
    return "\n".join(lines)


def setup(bot: commands.Bot) -> None:
    @bot.command(name="OMG", aliases=["omg"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def omg(ctx: commands.Context) -> None:
        """分析随 &OMG 上传的 OMG 选技截图并返回 T 级标注图。"""
        attachment = _find_image_attachment(ctx)
        if attachment is None:
            await ctx.send("请在 `&OMG` 指令后附加一张完整的 OMG 选技界面截图。")
            return
        if attachment.size and attachment.size > MAX_ATTACHMENT_BYTES:
            await ctx.send("截图文件过大，请上传不超过 12 MiB 的图片。")
            return

        status = await ctx.send("正在读取截图并生成 T 级标注，请稍候……")
        try:
            raw_image = await attachment.read()
            async with _processing_slots:
                result = await asyncio.wait_for(
                    asyncio.to_thread(process_omg_screenshot, raw_image),
                    timeout=PROCESS_TIMEOUT_SECONDS,
                )
            upload = discord.File(BytesIO(result.image), filename="omg-annotated.png")
            await ctx.reply(
                _format_result(result.recommendations, result.combo_recommendations),
                file=upload,
                mention_author=False,
            )
            await status.delete()
        except OmgInputError as exc:
            await status.edit(content=f"无法处理该截图：{exc}")
        except asyncio.TimeoutError:
            await status.edit(content="截图处理超时，请稍后重试或上传尺寸更小的截图。")
        except discord.HTTPException:
            await status.edit(content="标注已完成，但结果图片上传失败，请稍后重试。")
        except Exception as exc:
            print(f"[OMG] screenshot processing failed: {exc!r}")
            await status.edit(content="OMG 截图处理失败，后台已记录错误。")

    @omg.error
    async def omg_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"请求过于频繁，请在 {error.retry_after:.0f} 秒后重试。")
            return
        raise error
