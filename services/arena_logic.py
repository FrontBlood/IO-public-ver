# arena_logic.py

from collections import Counter

# 🧠 内存中的擂台状态（模块级变量）
arena_state = {
    "radiant_ids": [],     # 天辉频道当前成员
    "dire_ids": [],        # 夜魇频道当前成员
    "last_match_radiant": [],
    "last_match_dire": [],
    "last_win_ids": [],
    "streak": 0
}


def overlap(a, b):
    return len(set(a) & set(b))


def update_arena_state(radiant_ids, dire_ids):
    arena_state["radiant_ids"] = radiant_ids
    arena_state["dire_ids"] = dire_ids


def identify_winner():
    """
    根据频道阵容与上轮对战双方比较，判定哪一边是胜方。
    要求某一方与上轮阵容有 ≥4 名成员相同。
    返回: (胜方标识: 'radiant' 或 'dire')
    """
    last1 = arena_state["last_match_radiant"]
    last2 = arena_state["last_match_dire"]
    curr1 = arena_state["radiant_ids"]
    curr2 = arena_state["dire_ids"]

    radiant_score = max(overlap(curr1, last1), overlap(curr1, last2))
    dire_score = max(overlap(curr2, last1), overlap(curr2, last2))

    if radiant_score >= 4 and radiant_score > dire_score:
        return "radiant"
    elif dire_score >= 4 and dire_score > radiant_score:
        return "dire"
    return None


def settle_battle():
    """
    结算当前对局，记录胜方，处理擂主 streak，判断守擂成功。
    返回: 胜方名单、是否为擂主胜、是否守擂成功
    """
    winner = identify_winner()
    if not winner:
        return None, False, False

    winner_ids = arena_state["radiant_ids"] if winner == "radiant" else arena_state["dire_ids"]
    prev_ids = arena_state["last_win_ids"]

    is_defender = overlap(winner_ids, prev_ids) >= 4

    if is_defender:
        arena_state["streak"] += 1
    else:
        arena_state["streak"] = 1

    arena_state["last_win_ids"] = winner_ids
    arena_state["last_match_radiant"] = arena_state["radiant_ids"]
    arena_state["last_match_dire"] = arena_state["dire_ids"]

    defended = is_defender and arena_state["streak"] >= 3
    return winner_ids, is_defender, defended


def clear_arena():
    """关闭擂台，清空内存状态"""
    arena_state["radiant_ids"] = []
    arena_state["dire_ids"] = []
    arena_state["last_match_radiant"] = []
    arena_state["last_match_dire"] = []
    arena_state["last_win_ids"] = []
    arena_state["streak"] = 0
