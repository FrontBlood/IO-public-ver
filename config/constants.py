# 常量配置文件

# 公告频道 ID（请根据需要修改）
ANNOUNCE_CHANNEL_ID = 0  

#经验曲线设置
EXP_PARAMS = {
    "text": (3500, 2),
    "voice": (3500, 2),
    "stream": (3500, 2),
}

DAILY_CAP = {
    "text": 500,    # 每日最多文字经验
    "voice": 1000,  # 每日最多语音经验
    "stream": 2000  # 每日最多直播经验
}

MIN_XP_FLOOR = {
    "text": 2500,
    "voice": 5000,
    "stream": 10000
}

INACTIVITY_DAYS_THRESHOLD = 30

XP_DECAY_ENABLED = True

DEBUG_CHANNEL_ID = 0
COMMUNITY_MANAGER_ROLE_ID = 0
MESSAGE_DELETE_COMMAND_CHANNEL_ID = 0

DB_PATH = "levels.db"

CURRENCY_DB_PATH = "currency.db"

CURRENCY_NAME = "遗迹晶核"

# 签到数据库
CHECKIN_DB_PATH = "checkin.db"
CHECKIN_EVENT_DB_PATH = "checkin_event.db"
CHECKIN_EVENT_CHANNEL_ID = 0
CHECKIN_EVENT_REDEEM_CHANNEL_ID = 0
CHECKIN_EVENT_SIGNIN_CHANNEL_ID = 0
CHECKIN_EVENT_ADMIN_USER_ID = 0
CHECKIN_EVENT_REWARD_ROLE_ID = 0
CHECKIN_EVENT_REWARD_LIMIT = 30
CHECKIN_EVENT_REQUIRED_STREAK = 15
CHECKIN_EVENT_DURATION_DAYS = 30
CHECKIN_EVENT_DM_DELAY_SECONDS = 2.5
# config/constants.py

# 临时身份组配置
TEMP_PATH = "temp_roles.db"       # 👈 替换为你的 SQLite 数据文件路径

TEMP_NB_ROLE_ID = 0  # 👈 替换为你的真实萌新角色 ID
EXPIRE_AFTER_DAYS = 7              # 有效期天数
NEWBEEMANAGER_ROLE_ID = 0
# 商店相关
SHOP_DB_PATH = "shop.db"
SHOPADMIN_ROLE_ID = 0
# 掉落相关
DROP_ANNOUNCE_CHANNEL_ID = 0
DROP_ADMIN_ROLE_IDS = [
    0,  # 遗迹执行官
      # 备用权限组
]

ACHIEVEMENT_REWARDS = {
    "text_xp_1000": {"grant_xp": {"text": 100}, "grant_core": 2},
    "text_xp_3000": {"grant_xp": {"text": 200}, "grant_core": 3},
    "text_xp_5000": {"grant_xp": {"text": 300}, "grant_core": 5},
    "voice_xp_2000": {"grant_xp": {"voice": 150}, "grant_core": 2},
    "voice_xp_5000": {"grant_xp": {"voice": 300}, "grant_core": 4},
    "stream_xp_500": {"grant_xp": {"stream": 100}, "grant_core": 2},
    "stream_xp_2000": {"grant_xp": {"stream": 250}, "grant_core": 4},
    "total_level_5": {"grant_core": 3},
    "total_level_10": {"grant_core": 5},
    "checkin_3": {"grant_core": 2}
}

ARENA_DB_PATH = "arena.db"

# 私房状态数据库
PRIVATE_ROOM_DB_PATH = "private_rooms.db"
PRIVATE_ROOM_ACTIVE_CATEGORY_ID = 0
PRIVATE_ROOM_INACTIVE_CATEGORY_ID = 0
PRIVATE_ROOM_INACTIVITY_DAYS = 60
PRIVATE_ROOM_SWEEP_HOUR = 4
PRIVATE_ROOM_SWEEP_MINUTE = 40
PRIVATE_ROOM_MANAGE_CHANNELS_GUARD_ENABLED = True
