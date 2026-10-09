# config/achievement_definitions.py

from services.achievement_model import Achievement

ACHIEVEMENT_LIST = [
    # === 文字经验成就 ===
    Achievement(
        id="text_xp_1000",
        name="笔耕不辍",
        description="获得 1000 点文字经验",
        condition=lambda u, ctx=None: u.text_xp >= 1000,
        progress=lambda u, ctx=None: f"{u.text_xp}/1000",
        rewards={"core": 3, "xp": {"text": 100}}
    ),
    Achievement(
        id="text_xp_7000",
        name="文思泉涌",
        description="获得 7000 点文字经验",
        condition=lambda u, ctx=None: u.text_xp >= 7000,
        progress=lambda u, ctx=None: f"{u.text_xp}/7000",
        rewards={"core": 7, "xp": {"text": 200}},
        requires="text_xp_1000"
    ),
    Achievement(
        id="text_xp_50000",
        name="文学斗士",
        description="获得 50000 点文字经验",
        condition=lambda u, ctx=None: u.text_xp >= 50000,
        progress=lambda u, ctx=None: f"{u.text_xp}/50000",
        rewards={"core": 50, "xp": {"text": 5000}},
        requires="text_xp_7000"
    ),

    # === 语音经验成就 ===
    Achievement(
        id="voice_xp_2000",
        name="喋喋不休",
        description="获得 2000 点语音经验",
        condition=lambda u, ctx=None: u.voice_xp >= 2000,
        progress=lambda u, ctx=None: f"{u.voice_xp}/2000",
        rewards={"core": 5, "xp": {"voice": 200}}
    ),
    Achievement(
        id="voice_xp_14000",
        name="麦霸之魂",
        description="获得 14000 点语音经验",
        condition=lambda u, ctx=None: u.voice_xp >= 14000,
        progress=lambda u, ctx=None: f"{u.voice_xp}/14000",
        rewards={"core": 10, "xp": {"voice": 1400}},
        requires="voice_xp_2000"
    ),
    Achievement(
        id="voice_xp_50000",
        name="语者无敌",
        description="获得 50000 点语音经验",
        condition=lambda u, ctx=None: u.voice_xp >= 50000,
        progress=lambda u, ctx=None: f"{u.voice_xp}/50000",
        rewards={"core": 30, "xp": {"voice": 5000}},
        requires="voice_xp_14000"
    ),

    # === 直播经验成就 ===
    Achievement(
        id="stream_xp_4000",
        name="直播新星",
        description="获得 4000 点直播经验",
        condition=lambda u, ctx=None: u.stream_xp >= 4000,
        progress=lambda u, ctx=None: f"{u.stream_xp}/4000",
        rewards={"core": 5, "xp": {"stream": 400}}
    ),
    Achievement(
        id="stream_xp_14000",
        name="台前幕后",
        description="获得 14000 点直播经验",
        condition=lambda u, ctx=None: u.stream_xp >= 14000,
        progress=lambda u, ctx=None: f"{u.stream_xp}/14000",
        rewards={"core": 10, "xp": {"stream": 1400}},
        requires="stream_xp_4000"
    ),
    Achievement(
        id="stream_xp_50000",
        name="光影掌控者",
        description="获得 50000 点直播经验",
        condition=lambda u, ctx=None: u.stream_xp >= 50000,
        progress=lambda u, ctx=None: f"{u.stream_xp}/50000",
        rewards={"core": 30, "xp": {"stream": 5000}},
        requires="stream_xp_14000"
    ),

    # === 签到成就 ===
    Achievement(
        id="checkin_3",
        name="坚持不懈",
        description="连续签到 3 天",
        condition=lambda u, ctx=None: ctx and ctx.get("checkin_days", 0) >= 3,
        progress=lambda u, ctx=None: f"{ctx.get('checkin_days', 0)}/3",
        rewards={"core": 3}
    ),
    Achievement(
        id="checkin_7",
        name="持之以恒",
        description="连续签到 7 天",
        condition=lambda u, ctx=None: ctx and ctx.get("checkin_days", 0) >= 7,
        progress=lambda u, ctx=None: f"{ctx.get('checkin_days', 0)}/7",
        rewards={"core": 5},
        requires="checkin_3"
    ),
    Achievement(
        id="checkin_14",
        name="风雨无阻",
        description="连续签到 14 天",
        condition=lambda u, ctx=None: ctx and ctx.get("checkin_days", 0) >= 14,
        progress=lambda u, ctx=None: f"{ctx.get('checkin_days', 0)}/14",
        rewards={"core": 10},
        requires="checkin_7"
    ),
    Achievement(
        id="checkin_30",
        name="坚定如初",
        description="连续签到 30 天",
        condition=lambda u, ctx=None: ctx and ctx.get("checkin_days", 0) >= 30,
        progress=lambda u, ctx=None: f"{ctx.get('checkin_days', 0)}/30",
        rewards={"core": 15},
        requires="checkin_14"
    )
]
