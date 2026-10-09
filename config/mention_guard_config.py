MENTION_GUARD_ENABLED = True

# 全频提及门槛：总等级 >= 1 才能提及
MENTION_MIN_TOTAL_LEVEL = 1

# 例外组别：萌新可提及（绕过等级校验）
EXEMPT_ROLE_IDS = [
    0,
    0,
]

# 指定频道专管（可选，先留空）
CHANNEL_RULES = {
    0: {"mode": "deny_all"},
    # 123: {"mode": "deny_all"},
    # 456: {"mode": "min_level", "min_total_level": 3},
}

# 是否包含 Thread / Forum 帖子
INCLUDE_THREADS = True
