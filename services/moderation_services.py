# services/moderation_services.py
import os
import time
import hashlib
import asyncio
from typing import Any, Dict, Tuple, Optional

import discord
import aiohttp

from config.moderation_config import (
    MOD_GUARD_ENABLED,
    OPENAI_API_BASE,
    OPENAI_MODERATION_MODEL,
    MOD_REQUEST_TIMEOUT_SECS,
    MOD_MAX_RETRIES,
    MOD_SUSPICIOUS_MIN_LEN,
    MOD_SUSPICIOUS_KEYWORDS,
    MOD_WATCH_CHANNEL_IDS,
    MOD_EXCLUDE_CHANNEL_IDS,
    MOD_EXEMPT_ROLE_IDS,
    MOD_DELETE_SCORE_THRESHOLD,
    MOD_TARGET_CATEGORIES,
    MOD_CACHE_TTL_SECS,
    MOD_FAIL_OPEN,
)

# --------- module globals ---------
_session: Optional[aiohttp.ClientSession] = None
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}  # key -> (expire_ts, result_dict)
_cache_lock = asyncio.Lock()


def _get_api_key() -> Optional[str]:
    # 你可以用 OPENAI_API_KEY 或者你自己项目的 env 名
    return os.getenv("OPENAI_API_KEY")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
    if not role_ids:
        return False
    s = {r.id for r in member.roles}
    return any(rid in s for rid in role_ids)


def _in_scope(message: discord.Message) -> bool:
    ch_id = getattr(message.channel, "id", None)
    if ch_id is None:
        return False
    if ch_id in MOD_EXCLUDE_CHANNEL_IDS:
        return False
    if not MOD_WATCH_CHANNEL_IDS:
        return True  # 全频
    return ch_id in MOD_WATCH_CHANNEL_IDS


def _is_suspicious(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < MOD_SUSPICIOUS_MIN_LEN:
        return False
    # 可疑关键词（可逐步补强）
    for kw in MOD_SUSPICIOUS_KEYWORDS:
        if kw and kw in t:
            return True
    # 轻量启发式：包含明显对人输出的符号/结构，也可以触发
    if "你" in t and ("滚" in t or "死" in t):
        return True
    return bool(MOD_SUSPICIOUS_KEYWORDS) is False  # 如果你没填词库，就默认都送审（更严格）


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    timeout = aiohttp.ClientTimeout(total=MOD_REQUEST_TIMEOUT_SECS)
    _session = aiohttp.ClientSession(timeout=timeout)
    return _session


async def _moderate_text(text: str) -> Dict[str, Any]:
    """
    调用 OpenAI Moderations API:
    POST {OPENAI_API_BASE}/moderations
    body: { model, input }
    返回：results[0] 的结构（categories/category_scores/flagged...）
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = f"{OPENAI_API_BASE.rstrip('/')}/moderations"
    payload = {
        "model": OPENAI_MODERATION_MODEL,
        "input": text,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_err: Optional[Exception] = None
    for attempt in range(MOD_MAX_RETRIES + 1):
        try:
            sess = await _get_session()
            async with sess.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results") or []
                    if not results:
                        # 意外结构，按失败处理
                        raise RuntimeError("moderation empty results")
                    return results[0]
                # 429/5xx 做重试
                body = await resp.text()
                raise RuntimeError(f"moderation_http_{resp.status}: {body[:200]}")
        except Exception as e:
            last_err = e
            if attempt >= MOD_MAX_RETRIES:
                break
            # 指数退避
            await asyncio.sleep(0.2 * (2 ** attempt))
    raise last_err or RuntimeError("moderation_unknown_error")


async def moderate_and_decide(message: discord.Message) -> Tuple[bool, str, Dict[str, Any]]:
    """
    返回 (should_delete, reason, meta)
    meta: categories/category_scores/flagged 等结构，方便你后续写日志/计数/处罚。
    """
    if not MOD_GUARD_ENABLED:
        return (False, "mod_guard_disabled", {})

    if message.guild is None or message.author.bot:
        return (False, "ignore", {})

    if not _in_scope(message):
        return (False, "out_of_scope", {})

    if not isinstance(message.author, discord.Member):
        return (False, "not_member", {})

    # 白名单放行
    if _has_any_role(message.author, MOD_EXEMPT_ROLE_IDS):
        return (False, "exempt_role", {})

    text = (message.content or "").strip()
    if not text:
        return (False, "empty_text", {})

    # 只送审可疑消息（你可按需求调）
    if not _is_suspicious(text):
        return (False, "not_suspicious", {})

    # 缓存
    key = _hash_text(text)
    now = time.time()
    async with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > now:
            meta = cached[1]
            return _decide_from_meta(meta)

    # 云端审核
    try:
        meta = await _moderate_text(text)
    except Exception as e:
        if MOD_FAIL_OPEN:
            return (False, f"mod_error_fail_open:{type(e).__name__}", {"error": str(e)})
        return (True, f"mod_error_fail_closed:{type(e).__name__}", {"error": str(e)})

    # 写缓存
    async with _cache_lock:
        _cache[key] = (now + MOD_CACHE_TTL_SECS, meta)

    return _decide_from_meta(meta)


def _decide_from_meta(meta: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    meta: results[0] 结构
    """
    categories: Dict[str, bool] = meta.get("categories") or {}
    scores: Dict[str, float] = meta.get("category_scores") or {}
    flagged: bool = bool(meta.get("flagged", False))

    # 重点类别：只要命中且 score 足够高，就删
    hits = []
    max_hit = 0.0
    for cat in MOD_TARGET_CATEGORIES:
        if categories.get(cat) is True:
            sc = float(scores.get(cat, 0.0))
            hits.append((cat, sc))
            if sc > max_hit:
                max_hit = sc

    if hits and max_hit >= MOD_DELETE_SCORE_THRESHOLD:
        # 简短原因，方便你日志/统计
        top_cat = sorted(hits, key=lambda x: x[1], reverse=True)[0]
        return (True, f"mod_delete:{top_cat[0]}:{top_cat[1]:.2f}", {"flagged": flagged, "hits": hits, "scores": scores})

    # 如果整体 flagged 了，但分数不够高：先不删（只记录/累计次数更安全）
    if flagged:
        return (False, "mod_flagged_but_below_threshold", {"flagged": flagged, "scores": scores, "categories": categories})

    return (False, "mod_ok", {"flagged": flagged})
