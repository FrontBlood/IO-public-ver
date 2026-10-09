from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"


def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()


# Pillow ≥10.0 统一文本测量
def get_text_wh(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        return font.getsize(text)


# 深灰背景
def generate_esports_background(width=1200, height=720):
    base = Image.new("RGB", (width, height), (25, 25, 25))
    px = base.load()

    for _ in range(8000):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        c = random.randint(18, 35)
        px[x, y] = (c, c, c)

    return base.filter(ImageFilter.GaussianBlur(1.2))


def generate_mvp_image(
    blue_team,
    red_team,
    blue_name,
    red_name,
    output_path="mvp_result.png",
    final=False
):
    WIDTH = 1200
    HEIGHT = 720

    img = generate_esports_background(WIDTH, HEIGHT).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # 字体
    font_title = load_font(64)
    font_head = load_font(48)
    font_name = load_font(40)
    font_score = load_font(44)
    font_mvp = load_font(46)

    # 标题
    title = "MVP 票选结果" if final else "MVP 票选中"
    tw, th = get_text_wh(draw, title, font_title)
    draw.text(((WIDTH - tw) // 2, 30), title, fill=(255, 255, 255), font=font_title)

    # 渐变色条（红蓝）
    bar_h = 60
    blue_dark = (40, 80, 180)
    blue_light = (90, 150, 250)

    red_dark = (160, 30, 30)
    red_light = (230, 80, 80)

    # 左半蓝
    left_bar = Image.new("RGBA", (WIDTH // 2, bar_h))
    lb = ImageDraw.Draw(left_bar)
    for x in range(WIDTH // 2):
        t = x / (WIDTH // 2)
        c = (
            int(blue_dark[0] * (1 - t) + blue_light[0] * t),
            int(blue_dark[1] * (1 - t) + blue_light[1] * t),
            int(blue_dark[2] * (1 - t) + blue_light[2] * t),
        )
        lb.line([(x, 0), (x, bar_h)], fill=c)

    # 右半红
    right_bar = Image.new("RGBA", (WIDTH // 2, bar_h))
    rb = ImageDraw.Draw(right_bar)
    for x in range(WIDTH // 2):
        t = x / (WIDTH // 2)
        c = (
            int(red_light[0] * (1 - t) + red_dark[0] * t),
            int(red_light[1] * (1 - t) + red_dark[1] * t),
            int(red_light[2] * (1 - t) + red_dark[2] * t),
        )
        rb.line([(x, 0), (x, bar_h)], fill=c)

    img.paste(left_bar, (0, 120), left_bar)
    img.paste(right_bar, (WIDTH // 2, 120), right_bar)

    # 队名 & VS
    draw.text((100, 130), blue_name, fill=(255, 255, 255), font=font_head)
    draw.text((WIDTH - 350, 130), red_name, fill=(255, 255, 255), font=font_head)
    draw.text((WIDTH // 2 - 20, 130), "VS", fill=(255, 255, 0), font=font_head)

    # -------- 固定顺序，不排序 --------
    blue_fixed = blue_team[:5]
    red_fixed = red_team[:5]

    start_y = 220
    row_h = 75

    # 如果 final，则需要找到 MVP
    if final:
        all_players = blue_fixed + red_fixed
        mvp_name, mvp_votes = max(all_players, key=lambda x: x[1])
    else:
        mvp_name = None  # 不画框

    # 行绘制
    for i in range(5):
        y = start_y + i * row_h

        # 半透明行背景
        row_overlay = Image.new("RGBA", (WIDTH, row_h), (0, 0, 0, 0))
        ro = ImageDraw.Draw(row_overlay)
        for x in range(WIDTH):
            t = x / WIDTH
            lc = (
                int(blue_light[0] * (1 - t) + red_light[0] * t),
                int(blue_light[1] * (1 - t) + red_light[1] * t),
                int(blue_light[2] * (1 - t) + red_light[2] * t),
                40,
            )
            ro.line([(x, 0), (x, row_h)], fill=lc)

        img.paste(row_overlay, (0, y), row_overlay)

        b_name, b_vote = blue_fixed[i]
        r_name, r_vote = red_fixed[i]

        # --- 左侧蓝队名字 ---
        draw.text((80, y + 10), b_name, fill=(200, 255, 255), font=font_name)

        # --- 如果是 MVP，画金框 ---
        if final and b_name == mvp_name:
            w, h = get_text_wh(draw, b_name, font_name)
            frame = ImageDraw.Draw(img)
            frame.rectangle(
                (70, y + 12, 70 + w + 20, y + 12 + h + 20),
                outline=(255, 215, 0),
                width=4
            )

        # --- 右侧红队名字 ---
        draw.text((WIDTH - 350, y + 10), r_name, fill=(255, 200, 200), font=font_name)

        if final and r_name == mvp_name:
            w, h = get_text_wh(draw, r_name, font_name)
            frame = ImageDraw.Draw(img)
            frame.rectangle(
                (WIDTH - 360, y + 12, WIDTH - 360 + w + 20, y + 12 + h + 20),
                outline=(255, 215, 0),
                width=4
            )

        # --- 中间票数 ---
        score = f"{b_vote} : {r_vote}"
        sw, sh = get_text_wh(draw, score, font_score)
        draw.text(((WIDTH - sw) // 2, y + 10), score, fill=(255, 255, 255), font=font_score)

    img.convert("RGB").save(output_path)
    return output_path
