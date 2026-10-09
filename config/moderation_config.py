from config.constants import COMMUNITY_MANAGER_ROLE_ID

# config/moderation_config.py
# GPT Moderation（云端审核）配置

MOD_GUARD_ENABLED = True

# OpenAI
OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_MODERATION_MODEL = "omni-moderation-latest"

# 超时与重试
MOD_REQUEST_TIMEOUT_SECS = 4.0
MOD_MAX_RETRIES = 2

# 仅对“可疑消息”调用云端审核（节省请求/降低延迟）
# 命中这些条件之一才会送审；否则直接放行
MOD_SUSPICIOUS_MIN_LEN = 4
MOD_SUSPICIOUS_KEYWORDS = [
    # 你可以逐步补：常见脏话/侮辱词/威胁词/“你妈”等
]

# 监控范围（可选）
# 如果 WATCH 为空 => 全频（除了 EXCLUDE）
MOD_WATCH_CHANNEL_IDS: list[int] = []
MOD_EXCLUDE_CHANNEL_IDS: list[int] = []

# 例外（白名单）：这些 role 的成员永不因 AI 审核被删（比如管理员、管理组）
MOD_EXEMPT_ROLE_IDS: list[int] = [
    # 例如管理组role id
]

# “删消息”的判定阈值（0~1）
# 说明：Moderation 会给 categories(布尔) 和 category_scores(0~1)
# 我们用 score 做更细阈值控制，避免误杀
MOD_DELETE_SCORE_THRESHOLD = 0.90

# 哪些类别算“攻击性/人身攻击/威胁” —— 重点抓这几个
# 你也可以把 hate / violence 加进来
MOD_TARGET_CATEGORIES = [
    "harassment",
    "harassment/threatening",
    "hate",
    "hate/threatening",
    "violence",
    "violence/graphic",
]

# 缓存：同样文本短时间不重复送审（降低延迟/省请求）
MOD_CACHE_TTL_SECS = 0

# 失败策略：云端失败时是否放行
# True = 放行（推荐，避免误杀、避免阻塞）
MOD_FAIL_OPEN = True

# 图片诈骗审查：只处理带图片附件的消息。
SCAM_IMAGE_GUARD_ENABLED = True
SCAM_IMAGE_MODEL = "gpt-4.1-mini"
SCAM_IMAGE_PROMPT = (
    "Return only 1 or 0. "
    "1=MrBeast/Kogwin/KOG3500 crypto casino bonus,withdraw,or USDT proof scam image. "
    "0=otherwise."
)
SCAM_IMAGE_MAX_SIDE = 768
SCAM_IMAGE_JPEG_QUALITY = 82
SCAM_IMAGE_MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
SCAM_IMAGE_REQUEST_TIMEOUT_SECS = 12.0
SCAM_IMAGE_MAX_OUTPUT_TOKENS = 16
SCAM_IMAGE_USER_PASS_TTL_SECS = 60 * 60
SCAM_IMAGE_TIMEOUT_SECS = 24 * 60 * 60
SCAM_IMAGE_ALERT_CHANNEL_ID = 0
SCAM_IMAGE_ALERT_ROLE_ID = COMMUNITY_MANAGER_ROLE_ID
SCAM_IMAGE_CLEANUP_WINDOW_SECS = 3 * 60
