# ===== Mengmeng Module =====
MENGMENG_DB_PATH = "mengmeng.db"     # 萌萌独立数据库文件

MENGMENG_ROLE_ID = 0                # 萌萌身份组 role id
WELCOME_ROLE_ID = 0                 # 迎新身份组 role id

WELCOME_ADMIN_ROLE_ID = 0           # 可选：迎新管理role id，0表示仅管理员/Manage Guild

# 奖励/限制
MENGMENG_INITIAL_COINS = 10
MENGMENG_CHECKIN_STREAK_TARGET = 7
MENGMENG_CHECKIN_REWARD = 1
MENGMENG_LEVEL_TARGET = 5
MENGMENG_LEVEL_REWARD = 2

MENGMENG_VOICE_REWARD_SECONDS = 2 * 60 * 60   # 2小时
MENGMENG_VOICE_REWARD_COINS = 1
MENGMENG_VOICE_TOTAL_CAP = 7                  # ✅ 总共最多7枚（每天最多1枚）

MENGMENG_THANKS_DAILY_CAP = 4
MENGMENG_THANKS_COST = 1

# 播报间隔（秒）：每小时播报一次（发到语音频道文字聊天）
MENGMENG_RANK_BROADCAST_INTERVAL = 60 * 60
