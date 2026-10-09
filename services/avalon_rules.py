import random


GOOD = "GOOD"
EVIL = "EVIL"

MERLIN = "MERLIN"
PERCIVAL = "PERCIVAL"
LOYAL_SERVANT = "LOYAL_SERVANT"
ASSASSIN = "ASSASSIN"
MORGANA = "MORGANA"
MORDRED = "MORDRED"
OBERON = "OBERON"
MINION = "MINION"

ROLE_NAMES = {
    MERLIN: "梅林",
    PERCIVAL: "派西维尔",
    LOYAL_SERVANT: "亚瑟忠臣",
    ASSASSIN: "刺客",
    MORGANA: "莫甘娜",
    MORDRED: "莫德雷德",
    OBERON: "奥伯伦",
    MINION: "莫德雷德爪牙",
}

ROLE_SIDES = {
    MERLIN: GOOD,
    PERCIVAL: GOOD,
    LOYAL_SERVANT: GOOD,
    ASSASSIN: EVIL,
    MORGANA: EVIL,
    MORDRED: EVIL,
    OBERON: EVIL,
    MINION: EVIL,
}

SIDE_NAMES = {GOOD: "亚瑟阵营（好人）", EVIL: "莫德雷德阵营（坏人）"}

SIDE_COUNTS = {
    5: (3, 2),
    6: (4, 2),
    7: (4, 3),
    8: (5, 3),
    9: (6, 3),
    10: (6, 4),
}

AUTOMATIC_ROLE_SETTINGS = {
    5: {"percival": True, "morgana": True, "mordred": False, "oberon": False},
    6: {"percival": True, "morgana": True, "mordred": False, "oberon": False},
    7: {"percival": True, "morgana": True, "mordred": False, "oberon": True},
    8: {"percival": True, "morgana": True, "mordred": True, "oberon": False},
    9: {"percival": True, "morgana": True, "mordred": True, "oberon": False},
    10: {"percival": True, "morgana": True, "mordred": True, "oberon": True},
}

QUEST_TEAM_SIZES = {
    5: (2, 3, 2, 3, 3),
    6: (2, 3, 4, 3, 4),
    7: (2, 3, 3, 4, 4),
    8: (3, 4, 4, 5, 5),
    9: (3, 4, 4, 5, 5),
    10: (3, 4, 4, 5, 5),
}


def automatic_settings(player_count: int) -> dict:
    if player_count not in AUTOMATIC_ROLE_SETTINGS:
        raise ValueError("阿瓦隆需要 5 至 10 名玩家。")
    return dict(AUTOMATIC_ROLE_SETTINGS[player_count])

def side_for_role(role: str) -> str:
    return ROLE_SIDES[role]


def validate_settings(player_count: int, settings: dict) -> tuple[bool, str]:
    if player_count not in SIDE_COUNTS:
        return False, "阿瓦隆需要 5 至 10 名玩家。"

    good_count, evil_count = SIDE_COUNTS[player_count]
    good_specials = 1 + int(bool(settings.get("percival")))
    evil_specials = 1 + sum(
        int(bool(settings.get(key)))
        for key in ("morgana", "mordred", "oberon")
    )
    if good_specials > good_count:
        return False, "启用的好人特殊角色超过了本局好人人数。"
    if evil_specials > evil_count:
        return False, "启用的坏人特殊角色超过了本局坏人人数。"
    return True, ""


def build_role_deck(player_count: int, settings: dict, rng=None) -> list[str]:
    ok, message = validate_settings(player_count, settings)
    if not ok:
        raise ValueError(message)

    good_count, evil_count = SIDE_COUNTS[player_count]
    good_roles = [MERLIN]
    if settings.get("percival"):
        good_roles.append(PERCIVAL)
    good_roles.extend([LOYAL_SERVANT] * (good_count - len(good_roles)))

    evil_roles = [ASSASSIN]
    if settings.get("morgana"):
        evil_roles.append(MORGANA)
    if settings.get("mordred"):
        evil_roles.append(MORDRED)
    if settings.get("oberon"):
        evil_roles.append(OBERON)
    evil_roles.extend([MINION] * (evil_count - len(evil_roles)))

    deck = good_roles + evil_roles
    (rng or random.SystemRandom()).shuffle(deck)
    return deck


def quest_team_size(player_count: int, quest_index: int) -> int:
    return QUEST_TEAM_SIZES[player_count][quest_index]


def fails_required(player_count: int, quest_index: int) -> int:
    return 2 if player_count >= 7 and quest_index == 3 else 1


def quest_succeeds(player_count: int, quest_index: int, fail_count: int) -> bool:
    return fail_count < fails_required(player_count, quest_index)


def team_vote_passes(player_count: int, approve_count: int) -> bool:
    return approve_count > player_count / 2


def knowledge_for_player(user_id: str, roles: dict[str, str]) -> dict:
    role = roles[user_id]
    result = {"role": role, "side": side_for_role(role), "visible_players": []}

    if role == MERLIN:
        result["kind"] = "evil_except_mordred"
        result["visible_players"] = [
            uid
            for uid, other_role in roles.items()
            if side_for_role(other_role) == EVIL and other_role != MORDRED
        ]
    elif role == PERCIVAL:
        result["kind"] = "merlin_candidates"
        result["visible_players"] = [
            uid for uid, other_role in roles.items() if other_role in {MERLIN, MORGANA}
        ]
    elif side_for_role(role) == EVIL and role != OBERON:
        result["kind"] = "evil_allies_except_oberon"
        result["visible_players"] = [
            uid
            for uid, other_role in roles.items()
            if uid != user_id and side_for_role(other_role) == EVIL and other_role != OBERON
        ]
    else:
        result["kind"] = "none"

    return result
