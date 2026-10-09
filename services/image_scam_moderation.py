import asyncio
import base64
import hashlib
import io
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import discord
from PIL import Image

from config.moderation_config import (
    MOD_EXCLUDE_CHANNEL_IDS,
    MOD_WATCH_CHANNEL_IDS,
    OPENAI_API_BASE,
    SCAM_IMAGE_GUARD_ENABLED,
    SCAM_IMAGE_ALERT_CHANNEL_ID,
    SCAM_IMAGE_ALERT_ROLE_ID,
    SCAM_IMAGE_CLEANUP_WINDOW_SECS,
    SCAM_IMAGE_JPEG_QUALITY,
    SCAM_IMAGE_MAX_DOWNLOAD_BYTES,
    SCAM_IMAGE_MAX_OUTPUT_TOKENS,
    SCAM_IMAGE_MAX_SIDE,
    SCAM_IMAGE_MODEL,
    SCAM_IMAGE_PROMPT,
    SCAM_IMAGE_REQUEST_TIMEOUT_SECS,
    SCAM_IMAGE_TIMEOUT_SECS,
    SCAM_IMAGE_USER_PASS_TTL_SECS,
)


_session: aiohttp.ClientSession | None = None
_cache: dict[str, bool] = {}
_user_pass_cache: dict[int, float] = {}
_user_block_cache: dict[int, float] = {}
_cache_lock = asyncio.Lock()


def _get_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")


def log_scam_image_guard_status():
    status = "enabled" if SCAM_IMAGE_GUARD_ENABLED else "disabled"
    key_status = "set" if _get_api_key() else "missing"
    scope = "all_channels" if not MOD_WATCH_CHANNEL_IDS else f"watch={sorted(MOD_WATCH_CHANNEL_IDS)}"
    print(
        "[ScamImage] guard "
        f"{status}, api_key={key_status}, model={SCAM_IMAGE_MODEL}, scope={scope}, "
        f"exclude={sorted(MOD_EXCLUDE_CHANNEL_IDS)}"
    )


def _is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = (attachment.content_type or "").lower()
    if content_type.startswith("image/"):
        return True
    return attachment.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))


def has_image_attachment(message: discord.Message) -> bool:
    return any(_is_image_attachment(attachment) for attachment in message.attachments)


def describe_attachments(message: discord.Message) -> list[dict[str, Any]]:
    return [
        {
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size": attachment.size,
            "is_image": _is_image_attachment(attachment),
        }
        for attachment in message.attachments
    ]


def _in_scope(message: discord.Message) -> bool:
    channel_id = getattr(message.channel, "id", None)
    if channel_id is None:
        return False
    if channel_id in MOD_EXCLUDE_CHANNEL_IDS:
        return False
    if not MOD_WATCH_CHANNEL_IDS:
        return True
    return channel_id in MOD_WATCH_CHANNEL_IDS


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    timeout = aiohttp.ClientTimeout(total=SCAM_IMAGE_REQUEST_TIMEOUT_SECS)
    _session = aiohttp.ClientSession(timeout=timeout)
    return _session


async def _download_attachment(attachment: discord.Attachment) -> bytes | None:
    if attachment.size and attachment.size > SCAM_IMAGE_MAX_DOWNLOAD_BYTES:
        return None
    session = await _get_session()
    async with session.get(attachment.url) as response:
        if response.status != 200:
            return None
        data = await response.read()
    if len(data) > SCAM_IMAGE_MAX_DOWNLOAD_BYTES:
        return None
    return data


def _prepare_image(data: bytes) -> tuple[str, str]:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((SCAM_IMAGE_MAX_SIDE, SCAM_IMAGE_MAX_SIDE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=SCAM_IMAGE_JPEG_QUALITY, optimize=True)
    prepared = buffer.getvalue()
    digest = hashlib.sha256(prepared).hexdigest()
    b64 = base64.b64encode(prepared).decode("ascii")
    return digest, f"data:image/jpeg;base64,{b64}"


def _extract_output_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                chunks.append(content.get("text", ""))
    return "".join(chunks).strip()


async def _classify_image(image_url: str) -> tuple[bool, dict[str, Any]]:
    api_key = _get_api_key()
    if not api_key:
        return False, {"error": "OPENAI_API_KEY not set"}

    payload = {
        "model": SCAM_IMAGE_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": SCAM_IMAGE_PROMPT},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
        "max_output_tokens": SCAM_IMAGE_MAX_OUTPUT_TOKENS,
    }
    session = await _get_session()
    url = f"{OPENAI_API_BASE.rstrip('/')}/responses"
    print(f"[ScamImage] sending image to OpenAI model={SCAM_IMAGE_MODEL}")
    async with session.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    ) as response:
        body = await response.text()
        if response.status != 200:
            return False, {"error": f"responses_http_{response.status}", "body": body[:500]}
    data = await response.json()
    answer = _extract_output_text(data)
    print(f"[ScamImage] OpenAI answered={answer!r} usage={data.get('usage')}")
    return answer.startswith("1"), {"answer": answer, "usage": data.get("usage")}


async def should_delete_for_scam_image(message: discord.Message) -> tuple[bool, str, dict[str, Any]]:
    if not SCAM_IMAGE_GUARD_ENABLED:
        return False, "disabled", {}
    if message.guild is None or message.author.bot:
        return False, "ignore", {}
    if not _in_scope(message):
        return False, "out_of_scope", {}

    now = time.time()
    async with _cache_lock:
        block_until = _user_block_cache.get(message.author.id, 0)
        if block_until > now:
            return False, "user_recently_blocked", {"block_until": block_until}
        pass_until = _user_pass_cache.get(message.author.id, 0)
    if pass_until > now:
        return False, "user_recently_passed", {"pass_until": pass_until}

    attachments = [attachment for attachment in message.attachments if _is_image_attachment(attachment)]
    if not attachments:
        return False, "no_image", {}

    for attachment in attachments:
        try:
            raw = await _download_attachment(attachment)
            if not raw:
                continue
            digest, image_url = _prepare_image(raw)
            async with _cache_lock:
                cached = _cache.get(digest)
            if cached is not None:
                if cached:
                    return True, "scam_image_cache", {"sha256": digest}
                continue

            should_delete, meta = await _classify_image(image_url)
            async with _cache_lock:
                _cache[digest] = should_delete
            if should_delete:
                meta["sha256"] = digest
                async with _cache_lock:
                    _user_block_cache[message.author.id] = now + SCAM_IMAGE_TIMEOUT_SECS
                return True, "scam_image_ai", meta
            async with _cache_lock:
                _user_pass_cache[message.author.id] = now + SCAM_IMAGE_USER_PASS_TTL_SECS
        except Exception as exc:
            return False, f"scam_image_error:{type(exc).__name__}", {"error": str(exc)}

    return False, "scam_image_ok", {}


async def _timeout_member(message: discord.Message):
    if not isinstance(message.author, discord.Member):
        return
    until = datetime.now(timezone.utc) + timedelta(seconds=SCAM_IMAGE_TIMEOUT_SECS)
    try:
        await message.author.timeout(until, reason="scam_image_detected")
    except (discord.Forbidden, discord.HTTPException):
        pass


async def _send_alert(message: discord.Message, reason: str, meta: dict[str, Any]):
    channel = message.guild.get_channel(SCAM_IMAGE_ALERT_CHANNEL_ID) if message.guild else None
    if channel is None:
        return
    await channel.send(
        f"<@&{SCAM_IMAGE_ALERT_ROLE_ID}> 检测到疑似诈骗图片，已删除消息并禁言 1 天。\n"
        f"用户：{message.author.mention} (`{message.author.id}`)\n"
        f"频道：<#{message.channel.id}>\n"
        f"原因：`{reason}`",
        allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
    )


async def _cleanup_recent_user_messages(message: discord.Message) -> int:
    if not message.guild:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SCAM_IMAGE_CLEANUP_WINDOW_SECS)
    deleted_count = 0

    def should_delete(candidate: discord.Message) -> bool:
        return candidate.author.id == message.author.id and candidate.created_at >= cutoff

    for channel in message.guild.text_channels:
        permissions = channel.permissions_for(message.guild.me)
        if not permissions.manage_messages or not permissions.read_message_history:
            continue
        try:
            deleted = await channel.purge(
                limit=100,
                check=should_delete,
                after=cutoff,
                bulk=True,
                reason="scam_image_recent_cleanup",
            )
            deleted_count += len(deleted)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            continue
    return deleted_count


async def moderate_image_message_later(message: discord.Message):
    delete, reason, meta = await should_delete_for_scam_image(message)
    if not delete:
        print(
            "[ScamImage] skipped "
            f"message={message.id} author={message.author.id} channel={message.channel.id} "
            f"reason={reason} meta={meta} attachments={describe_attachments(message)}"
        )
        return
    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass
    await _timeout_member(message)
    cleanup_count = await _cleanup_recent_user_messages(message)
    meta["cleanup_count"] = cleanup_count
    await _send_alert(message, reason, meta)
    print(
        "[ScamImage] deleted "
        f"message={message.id} author={message.author.id} channel={message.channel.id} "
        f"reason={reason} meta={meta}"
    )
