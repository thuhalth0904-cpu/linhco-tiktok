"""Dựng hình video lịch ngày 1080×1920, 30 khung hình/giây, theo thời lượng giọng đọc.

Dùng: python render.py script.json timing.json out.mp4
Phông chữ: FONT_DIR chứa BeVietnamPro-SemiBold.ttf, BeVietnamPro-Bold.ttf, PlayfairDisplay-VF.ttf.
Toàn bộ hình vẽ bằng mã (không dùng ảnh AI), màu và phông theo nhận diện của web Linh Cơ.
"""
import json
import math
import os
import random
import subprocess
import sys
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
CX = 505                      # tâm nội dung, lệch trái tránh cột nút của TikTok
SUB_Y = 1360                  # phụ đề nằm trên vùng 400 px dưới cùng
GOLD, GOLD_SOFT, CREAM = (232, 196, 106), (243, 228, 184), (251, 245, 232)
RED, RED_DARK, INK = (126, 29, 29), (70, 12, 14), (43, 33, 28)
GREEN, BAD = (30, 123, 52), (183, 28, 28)
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.environ.get("FONT_DIR", os.path.join(HERE, "fonts"))
GAP, LEAD = 0.35, 0.25        # nghỉ giữa các câu; giọng vào sau khi cảnh hiện 0.25 s
MIN_DUR = {"hook": 3.0, "title": 2.6, "hours": 3.6, "cta": 3.6, "xung": 2.6}


@lru_cache(maxsize=64)
def font(kind: str, size: int):
    if kind == "serif":
        f = ImageFont.truetype(os.path.join(FONT_DIR, "PlayfairDisplay-VF.ttf"), size)
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
        return f
    name = "BeVietnamPro-Bold.ttf" if kind == "bold" else "BeVietnamPro-SemiBold.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def back(x):  # bật nhẹ khi xuất hiện
    x = max(0.0, min(1.0, x))
    c = 1.4
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def tw(d, text, f):
    return d.textlength(text, font=f)


def ctext(d, y, text, f, fill, cx=CX, stroke=0, sfill=None):
    d.text((cx - tw(d, text, f) / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if tw(d, t, f) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def balanced(d, text, f, maxw):
    """Ngắt dòng cân đối, không để chữ lẻ một mình ở dòng cuối."""
    lines = wrap(d, text, f, maxw)
    if len(lines) < 2:
        return lines
    n = len(lines)
    lo, hi = maxw * 0.5, maxw
    best = lines
    for _ in range(14):
        mid = (lo + hi) / 2
        t = wrap(d, text, f, mid)
        if len(t) <= n:
            best, hi = t, mid
        else:
            lo = mid
    return best


# ——— Nền chuyển động ———
@lru_cache(maxsize=1)
def base_bg():
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    top, mid, bot = np.array([90, 18, 20]), np.array([143, 38, 34]), np.array([52, 10, 12])
    t = y.repeat(W, 1)[..., None]
    g = np.where(t < 0.45, top + (mid - top) * (t / 0.45), mid + (bot - mid) * ((t - 0.45) / 0.55))
    r = np.hypot((x - 0.5) * 1.2, (y - 0.42))[..., None]
    g = g * (1.05 - 0.45 * np.clip(r, 0, 1))
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8))


@lru_cache(maxsize=1)
def lotus_img():
    p = os.path.join(HERE, "../../web/public/lotus.png")
    im = Image.open(p).convert("RGBA")
    big = im.resize((820, int(820 * im.height / im.width)), Image.LANCZOS)
    a = big.getchannel("A").point(lambda v: int(v * 0.10))
    big.putalpha(a)
    return big


rng = random.Random(7)
DUST = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.5, 4.5), rng.uniform(18, 60), rng.uniform(0, 6.28)) for _ in range(70)]


def background(t):
    im = base_bg().convert("RGBA")
    lt = lotus_img().rotate(math.sin(t * 0.25) * 4, resample=Image.BICUBIC, expand=False)
    im.alpha_composite(lt, (CX - lt.width // 2, 560 - lt.height // 2 + int(math.sin(t * 0.4) * 10)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x0, y0, r, sp, ph in DUST:
        y = (y0 - t * sp) % (H + 40) - 20
        x = x0 + math.sin(t * 0.6 + ph) * 18
        a = int(120 + 100 * math.sin(t * 1.3 + ph))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(243, 213, 139, max(30, a)))
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.2)))
    return im


@lru_cache(maxsize=4)
def header(sub="Lịch âm hôm nay"):
    lay = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    icon = Image.open(os.path.join(HERE, "../../web/public/favicon.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
    f = font("serif", 46)
    label = "linhco.vn"
    sub = "  ·  " + sub
    fs = font("semi", 30)
    total = 64 + 16 + tw(d, label, f) + tw(d, sub, fs)
    x = CX - total / 2
    lay.alpha_composite(icon, (int(x), 33))
    d.text((x + 80, 28), label, font=f, fill=GOLD_SOFT)
    d.text((x + 80 + tw(d, label, f), 44), sub, font=fs, fill=(248, 238, 220))
    return lay


def card(w, h, fill=CREAM, radius=34, border=GOLD):
    lay = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((30, 40, w + 30, h + 40), radius, fill=(0, 0, 0, 120))
    lay = lay.filter(ImageFilter.GaussianBlur(14))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((30, 30, w + 30, h + 30), radius, fill=fill + (255,), outline=border + (255,), width=4)
    return lay


def paste(base, lay, x, y, alpha=1.0, scale=1.0):
    if alpha <= 0.01:
        return
    if scale != 1.0:
        lay = lay.resize((max(1, int(lay.width * scale)), max(1, int(lay.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        lay = lay.copy()
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
    base.alpha_composite(lay, (int(x - lay.width / 2), int(y - lay.height / 2)))


# ——— Các cảnh. tl: thời gian trong cảnh, dur: độ dài cảnh ———
def s_hook(base, d, ln, tl, dur):
    s, l = d["solar"], d["lunar"]
    lay = card(820, 640)
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 70, d["weekday"].upper(), font("bold", 44), RED, cx)
    num = str(s["day"])
    fnum = font("serif", 250)
    rest = f"/{s['month']}/{s['year']}"
    fr = font("serif", 66)
    wtot = tw(g, num, fnum) + tw(g, rest, fr)
    x0 = cx - wtot / 2
    g.text((x0, 120), num, font=fnum, fill=RED)
    g.text((x0 + tw(g, num, fnum), 315), rest, font=fr, fill=RED)
    # huy hiệu âm lịch
    g.ellipse((cx - 210, 440, cx - 70, 580), fill=GOLD + (255,), outline=(170, 130, 40, 255), width=4)
    ctext(g, 452, str(l["day"]), font("serif", 72), RED_DARK, cx - 140)
    ctext(g, 540, f"tháng {l['month']}", font("semi", 24), RED_DARK, cx - 140)
    g.text((cx - 50, 470), "Âm lịch", font=font("semi", 32), fill=(110, 98, 90))
    g.text((cx - 50, 512), f"năm {d['yearCanChi']}", font=font("bold", 40), fill=INK)
    paste(base, lay, CX, 640, 1.0, 1.0 + 0.03 * ease(tl / 3.0))
    # câu mở đầu nổi bật
    hook = ln["sub"]
    f = font("bold", 56)
    lay2 = Image.new("RGBA", (W, 330), (0, 0, 0, 0))
    g2 = ImageDraw.Draw(lay2)
    lines = balanced(g2, hook, f, 860)
    y = 165 - len(lines) * 37
    for t in lines:
        ctext(g2, y, t, f, GOLD_SOFT, W / 2 - (W / 2 - CX), stroke=3, sfill=(60, 10, 10))
        y += 74
    paste(base, lay2, W / 2, 1150, 1.0)


def row_card(title, rows, tl, base, y_center, accent=RED):
    """Thẻ có tiêu đề và các dòng hiện lần lượt."""
    lay = card(860, 140 + 110 * len(rows))
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 58, title, font("serif", 54), accent, cx)
    g.line((cx - 120, 132, cx + 120, 132), fill=GOLD + (255,), width=3)
    return lay


def s_date(base, d, ln, tl, dur):
    l = d["lunar"]
    rows = [("Âm lịch", f"{l['day']}/{l['month']}{' nhuận' if l['leap'] else ''} · năm {d['yearCanChi']}"),
            ("Ngày", d["dayCanChi"]), ("Tháng", d["monthCanChi"]), ("Tiết khí", d["solarTerm"])]
    lay = card(860, 170 + 112 * len(rows))
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 60, "Ngày mai theo âm lịch", font("serif", 52), RED, cx)
    paste(base, lay, CX, 760, min(1, tl / 0.3), 0.92 + 0.08 * back(tl / 0.5))
    step = max(0.35, (dur - 1.0) / len(rows))
    for i, (k, v) in enumerate(rows):
        a = ease((tl - 0.3 - i * step * 0.6) / 0.35)
        if a <= 0:
            continue
        lr = Image.new("RGBA", (800, 96), (0, 0, 0, 0))
        gr = ImageDraw.Draw(lr)
        gr.rounded_rectangle((0, 0, 799, 95), 22, fill=(248, 238, 220, 255))
        gr.text((30, 26), k, font=font("semi", 36), fill=(110, 98, 90))
        fv = font("bold", 44)
        gr.text((770 - tw(gr, v, fv), 20), v, font=fv, fill=INK)
        top = 760 - lay.height / 2 + 30 + 150 + i * 112
        paste(base, lr, CX + (1 - a) * 60, top + 48, a)


def s_god(base, d, ln, tl, dur):
    good = d["hoangDao"]
    lay = card(860, 640, fill=(255, 250, 238))
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    badge = "NGÀY HOÀNG ĐẠO" if good else "NGÀY HẮC ĐẠO"
    bcol = (36, 120, 60) if good else (60, 40, 40)
    fb = font("bold", 50)
    bw = tw(g, badge, fb) + 80
    g.rounded_rectangle((cx - bw / 2, 70, cx + bw / 2, 160), 45, fill=bcol + (255,))
    ctext(g, 88, badge, fb, (255, 255, 255), cx)
    ctext(g, 200, d["dayGod"], font("serif", 120), RED, cx)
    ctext(g, 370, f"Trực {d['truc']}", font("semi", 46), INK, cx)
    warn = []
    if d.get("tamNuong"):
        warn.append("Trùng ngày Tam Nương")
    if d.get("nguyetKy"):
        warn.append("Ngày Nguyệt Kỵ")
    y = 470
    for wtxt in warn:
        fw = font("bold", 40)
        ww = tw(g, wtxt, fw) + 70
        g.rounded_rectangle((cx - ww / 2, y, cx + ww / 2, y + 74), 37, fill=(251, 233, 231, 255), outline=BAD + (255,), width=3)
        ctext(g, y + 14, wtxt, fw, BAD, cx)
        y += 88
    pulse = 1 + 0.02 * math.sin(tl * 6) if warn else 1
    paste(base, lay, CX, 760, min(1, tl / 0.3), (0.85 + 0.15 * back(tl / 0.55)) * pulse)


def s_hours(base, d, ln, tl, dur):
    hours = d["goodHours"]
    lay = card(880, 760)
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 60, "Giờ hoàng đạo", font("serif", 58), RED, cx)
    paste(base, lay, CX, 780, min(1, tl / 0.3))
    cols = 3
    tile_w, tile_h = 250, 230
    x0 = CX - (cols * tile_w + (cols - 1) * 24) / 2
    y0 = 780 - 760 / 2 + 30 + 170
    step = min(0.3, max(0.15, (dur - 1.2) / max(1, len(hours))))
    for i, h in enumerate(hours):
        a = (tl - 0.5 - i * step) / 0.35
        if a <= 0:
            continue
        r, c = divmod(i, cols)
        lt = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        gt = ImageDraw.Draw(lt)
        gt.rounded_rectangle((0, 0, tile_w - 1, tile_h - 1), 28, fill=(253, 244, 220, 255), outline=GOLD + (255,), width=4)
        ctext(gt, 36, h["chi"], font("serif", 76), RED, tile_w / 2)
        ctext(gt, 150, h["range"].replace("–", " – "), font("semi", 34), INK, tile_w / 2)
        x = x0 + c * (tile_w + 24) + tile_w / 2
        y = y0 + r * (tile_h + 24) + tile_h / 2
        paste(base, lt, x, y, ease(a), 0.6 + 0.4 * back(a))


def s_list(base, d, ln, tl, dur, title, items, color, mark):
    lay = card(860, 180 + 118 * len(items))
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 60, title, font("serif", 60), color, cx)
    yc = 780
    paste(base, lay, CX, yc, min(1, tl / 0.3), 0.92 + 0.08 * back(tl / 0.5))
    step = min(0.35, max(0.2, (dur - 1.0) / max(1, len(items))))
    for i, it in enumerate(items):
        a = ease((tl - 0.4 - i * step) / 0.35)
        if a <= 0:
            continue
        lr = Image.new("RGBA", (780, 100), (0, 0, 0, 0))
        gr = ImageDraw.Draw(lr)
        gr.ellipse((10, 14, 82, 86), fill=color + (255,))
        if mark == "✓":
            gr.line([(28, 52), (42, 66), (66, 36)], fill=(255, 255, 255), width=9, joint="curve")
        else:
            gr.line([(30, 34), (62, 66)], fill=(255, 255, 255), width=9)
            gr.line([(62, 34), (30, 66)], fill=(255, 255, 255), width=9)
        text = it[:1].upper() + it[1:]
        size = 50
        while size > 30 and tw(gr, text, font("bold", size)) > 650:
            size -= 2
        fi = font("bold", size)
        gr.text((110, 20), text, font=fi, fill=INK)
        top = yc - lay.height / 2 + 30 + 170 + i * 118
        paste(base, lr, CX - (1 - a) * 80, top + 50, a)


def items_of(s):
    return [x.strip() for x in s.split(",") if x.strip()][:4]


def s_do(base, d, ln, tl, dur):
    s_list(base, d, ln, tl, dur, "Nên làm", items_of(d["shouldDo"]), GREEN, "✓")


def s_avoid(base, d, ln, tl, dur):
    s_list(base, d, ln, tl, dur, "Nên tránh", items_of(d["shouldAvoid"]), BAD, "✕")


DIRS = {"Chính Bắc": 0, "Đông Bắc": 45, "Chính Đông": 90, "Đông Nam": 135, "Chính Nam": 180, "Tây Nam": 225, "Chính Tây": 270, "Tây Bắc": 315}


def s_dir(base, d, ln, tl, dur):
    lay = card(860, 860)
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 56, "Hướng xuất hành", font("serif", 58), RED, cx)
    ccy, R = 410, 230
    g.ellipse((cx - R, ccy - R, cx + R, ccy + R), fill=(253, 244, 220, 255), outline=GOLD + (255,), width=6)
    g.ellipse((cx - R + 36, ccy - R + 36, cx + R - 36, ccy + R - 36), outline=(230, 210, 160, 255), width=2)
    for name, lbl in (("Chính Bắc", "Bắc"), ("Chính Nam", "Nam"), ("Chính Đông", "Đông"), ("Chính Tây", "Tây")):
        a = math.radians(DIRS[name])
        x = cx + math.sin(a) * (R - 18)
        y = ccy - math.cos(a) * (R - 18)
        fl = font("bold", 28)
        g.rounded_rectangle((x - tw(g, lbl, fl) / 2 - 8, y - 20, x + tw(g, lbl, fl) / 2 + 8, y + 20), 10, fill=(253, 244, 220, 255))
        ctext(g, y - 18, lbl, fl, (110, 98, 90), x)
    items = [("hyThan", "Hỷ Thần", (200, 150, 30)), ("taiThan", "Tài Thần", (183, 28, 28))]
    for k, (key, label, col) in enumerate(items):
        y = 690 + k * 76
        g.ellipse((cx - 300, y + 8, cx - 260, y + 48), fill=col + (255,))
        g.text((cx - 240, y), f"{label}: {d[key]}", font=font("bold", 46), fill=col)
    top = 800 - lay.height / 2
    paste(base, lay, CX, 800, min(1, tl / 0.3))
    ox, oy = CX, top + 30 + ccy
    g2 = ImageDraw.Draw(base)
    for k, (key, label, col) in enumerate(items):
        ang = DIRS.get(d[key])
        a = ease((tl - 0.5 - k * max(0.6, dur * 0.3)) / 0.5)
        if ang is None or a <= 0:
            continue
        rad = math.radians(ang)
        L = (R - 64) * a
        ex, ey = ox + math.sin(rad) * L, oy - math.cos(rad) * L
        g2.line((ox, oy, ex, ey), fill=col, width=16)
        left = (ex + math.sin(rad + 2.6) * 44, ey - math.cos(rad + 2.6) * 44)
        right = (ex + math.sin(rad - 2.6) * 44, ey - math.cos(rad - 2.6) * 44)
        g2.polygon([(ex + math.sin(rad) * 10, ey - math.cos(rad) * 10), left, right], fill=col)
    g2.ellipse((ox - 16, oy - 16, ox + 16, oy + 16), fill=RED)


def s_cta(base, d, ln, tl, dur):
    lay = card(860, 700, fill=(255, 250, 238))
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    icon = Image.open(os.path.join(HERE, "../../web/public/favicon.png")).convert("RGBA").resize((170, 170), Image.LANCZOS)
    lay.alpha_composite(icon, (int(cx - 85), 70))
    ctext(g, 270, "linhco.vn", font("serif", 104), RED, cx)
    ctext(g, 420, "Lịch âm · Tử vi · Giải mộng", font("bold", 50), INK, cx)
    ctext(g, 510, "Lịch âm, giờ tốt mỗi ngày", font("semi", 42), (110, 98, 90), cx)
    ctext(g, 580, "Theo dõi để xem lịch mỗi ngày!", font("bold", 42), RED, cx)
    paste(base, lay, CX, 780, min(1, tl / 0.3), 0.88 + 0.12 * back(tl / 0.6))


CHI12 = "Tý Sửu Dần Mão Thìn Tỵ Ngọ Mùi Thân Dậu Tuất Hợi".split()


def s_xung(base, d, ln, tl, dur):
    chi = d["dayCanChi"].split()[-1]
    x = CHI12[(CHI12.index(chi) + 6) % 12]
    lay = card(820, 560, fill=(255, 250, 238))
    g = ImageDraw.Draw(lay)
    cx = lay.width / 2
    ctext(g, 64, "Tuổi xung hôm nay", font("serif", 56), RED, cx)
    g.ellipse((cx - 150, 160, cx + 150, 460), fill=(251, 233, 231, 255), outline=BAD + (255,), width=6)
    ctext(g, 230, x, font("serif", 120), BAD, cx)
    ctext(g, 500, f"Ngày {d['dayCanChi']}", font("semi", 38), (110, 98, 90), cx)
    paste(base, lay, CX, 800, min(1, tl / 0.3), 0.85 + 0.15 * back(tl / 0.55))


def s_story(base, d, ln, tl, dur):
    pass  # chỉ có ảnh nền và phụ đề


def s_title(base, d, ln, tl, dur):
    """Mở đầu kiểu kể chuyện: tiêu đề lớn trên ảnh, kèm ngày."""
    title = ln.get("title") or ln["sub"]
    f = font("serif", 92)
    lay = Image.new("RGBA", (W, 760), (0, 0, 0, 0))
    g = ImageDraw.Draw(lay)
    lines = balanced(g, title.upper() if len(title) < 18 else title, f, 900)
    y = 380 - len(lines) * 58
    for t in lines:
        ctext(g, y, t, f, GOLD_SOFT, CX, stroke=5, sfill=(40, 8, 8))
        y += 116
    if d.get("topic"):
        chip = d["group"]
    else:
        s, l = d["solar"], d["lunar"]
        chip = f"{d['weekday']} {s['day']}/{s['month']}  ·  {l['day']}/{l['month']} âm lịch"
    fc = font("bold", 40)
    cw = tw(g, chip, fc) + 70
    g.rounded_rectangle((CX - cw / 2, y + 30, CX + cw / 2, y + 112), 41, fill=(126, 29, 29, 235), outline=GOLD + (255,), width=3)
    ctext(g, y + 46, chip, fc, (255, 246, 228), CX)
    # hiện rõ ngay từ khung hình đầu (người xem quyết định lướt hay ở lại trong 1 giây)
    paste(base, lay, W / 2, 760, 1.0, 1.0 + 0.04 * ease(tl / 3.0))


SCENES = {"hook": s_hook, "date": s_date, "god": s_god, "hours": s_hours, "do": s_do, "avoid": s_avoid, "dir": s_dir,
          "cta": s_cta, "xung": s_xung, "story": s_story, "title": s_title}
CARD_SCENES = {"date", "god", "hours", "do", "avoid", "dir", "cta", "xung"}


# ——— Ảnh nền theo ngày, chuyển động chậm (zoom/trôi) ———
@lru_cache(maxsize=8)
def photo(path):
    im = Image.open(path).convert("RGB")
    sc = max(W / im.width, H / im.height) * 1.14
    return im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)


@lru_cache(maxsize=1)
def shade():
    """Phủ tối trên/dưới để chữ dễ đọc."""
    y = np.linspace(0, 1, H)[:, None]
    a = 0.30 + 0.45 * np.clip((y - 0.55) / 0.45, 0, 1) + 0.35 * np.clip((0.18 - y) / 0.18, 0, 1)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (np.clip(a, 0, 0.85) * 255).astype(np.uint8).repeat(W, 1)
    return Image.fromarray(arr, "RGBA")


def kenburns(path, u, k):
    """u: tiến độ 0..1 trong cảnh; k: số thứ tự để đổi hướng chuyển động."""
    im = photo(path)
    z = 1.0 + 0.10 * (u if k % 2 == 0 else 1 - u)
    w, h = W * (im.width / W) / z, H * (im.height / H) / z
    w, h = min(w, im.width), min(h, im.height)
    pan = (u - 0.5) * (1 if k % 3 else -1)
    x0 = (im.width - w) / 2 + pan * (im.width - w) * 0.8
    y0 = (im.height - h) * 0.45
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h)).convert("RGBA")


def photo_bg(scenes, t, i, tl):
    sc = scenes[i]
    cur = kenburns(sc["img"], min(1, tl / max(sc["dur"], 0.1)), sc["imgk"])
    if i > 0 and scenes[i - 1]["img"] != sc["img"] and tl < 0.45:
        pv = scenes[i - 1]
        prev = kenburns(pv["img"], 1.0, pv["imgk"])
        cur = Image.blend(prev, cur, ease(tl / 0.45))
    cur.alpha_composite(shade())
    if sc["line"]["scene"] in CARD_SCENES:
        cur.alpha_composite(Image.new("RGBA", (W, H), (20, 6, 4, 90)))
    return cur


def chunks(text, maxw=17):
    """Chia phụ đề dài thành từng đoạn ngắn theo dấu câu."""
    import re
    parts = [p.strip() for p in re.split(r"(?<=[.!?:,;])\s+", text) if p.strip()]
    out, cur = [], ""
    for p in parts:
        cand = (cur + " " + p).strip()
        if cur and len(cand.split()) > maxw:
            out.append(cur)
            cur = p
        else:
            cur = cand
    if cur:
        out.append(cur)
    res = []
    for c in out:  # đoạn vẫn quá dài thì cắt đôi theo số chữ
        w = c.split()
        while len(w) > maxw + 4:
            res.append(" ".join(w[:maxw]))
            w = w[maxw:]
        res.append(" ".join(w))
    return res


@lru_cache(maxsize=64)
def subtitle_img(text, big=False):
    f = font("bold", 54 if big else 46)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = balanced(tmp, text, f, 880)
    lh = 72 if big else 62
    w = int(max(tw(tmp, l, f) for l in lines)) + 70
    h = lh * len(lines) + 40
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = ImageDraw.Draw(lay)
    g.rounded_rectangle((0, 0, w - 1, h - 1), 26, fill=(28, 12, 8, 205), outline=(214, 172, 92, 220), width=2)
    for i, t in enumerate(lines):
        ctext(g, 18 + i * lh, t, f, (255, 250, 240), w / 2)
    return lay


def plan(script, timing):
    t = 0.0
    out = []
    imgs = script.get("images") or []
    k = 0
    cur = 0
    for ln, tm in zip(script["lines"], timing["lines"]):
        sc = ln["scene"]
        dur = max(MIN_DUR.get(sc, 2.0 if sc == "story" else 2.4), LEAD + tm["dur"] + GAP)
        if imgs:
            if sc in ("title", "hook") and not out:
                cur = 0
            elif sc == "story" or (sc in CARD_SCENES and out and out[-1]["line"]["scene"] not in CARD_SCENES):
                cur = (cur + 1) % len(imgs) if len(imgs) > 1 else 0
                k += 1
        out.append({"line": ln, "start": round(t, 3), "dur": round(dur, 3), "voice_at": round(t + LEAD, 3), "file": tm["file"],
                    "img": imgs[cur] if imgs else None, "imgk": k})
        t += dur
    return out, t + 0.6


def frame(script, scenes, t):
    d = script["day"]
    idx = max(i for i, sc in enumerate(scenes) if sc["start"] <= t or i == 0)
    if scenes[idx]["img"]:
        base = photo_bg(scenes, t, idx, t - scenes[idx]["start"])
    else:
        base = background(t)
    base.alpha_composite(header(d.get("group") or "Lịch âm hôm nay"), (0, 150))
    for i, sc in enumerate(scenes):
        tl = t - sc["start"]
        last = i == len(scenes) - 1
        if 0 <= tl < sc["dur"] + (0.6 if last else 0):
            fade = 1.0 if last else ease((sc["dur"] - tl) / 0.22)
            kind = sc["line"]["scene"]
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            SCENES[kind](layer, d, sc["line"], tl, sc["dur"])
            if fade < 0.999:
                layer.putalpha(layer.getchannel("A").point(lambda v: int(v * fade)))
            base.alpha_composite(layer)
            if kind == "hook":
                continue
            story = kind in ("story", "title")
            parts = chunks(sc["line"]["sub"]) if story else chunks(sc["line"]["sub"], 11)
            # đoạn phụ đề chạy theo tỉ lệ số ký tự trên thời lượng giọng
            vd = max(0.5, sc["dur"] - LEAD - GAP)
            tot = sum(len(p) for p in parts)
            acc, j = 0.0, 0
            for j, p in enumerate(parts):
                acc += len(p) / tot * vd
                if tl - LEAD < acc:
                    break
            sub = subtitle_img(parts[j], story)
            sa = min(ease((tl - LEAD + 0.1) / 0.2), fade)
            if sa > 0:
                y = 1240 if kind == "story" else (1270 if kind == "title" else SUB_Y)
                paste(base, sub, CX, y + sub.height / 2, sa)
    base.alpha_composite(bottom_band(), (0, BAND_Y))
    return base.convert("RGB")


BAND_Y = 1572  # ngay trên vùng TikTok/YouTube che (tên kênh, mô tả)


@lru_cache(maxsize=1)
def bottom_band():
    """Dải cố định: linhco.vn + các tiện ích miễn phí."""
    f1, f2 = font("bold", 40), font("semi", 29)
    l1, l2 = "linhco.vn", "Lịch âm · Tử vi · Giải mộng · Văn khấn · Miễn phí"
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    w = int(max(tw(tmp, l1, f1), tw(tmp, l2, f2))) + 64
    lay = Image.new("RGBA", (W, 104), (0, 0, 0, 0))
    g = ImageDraw.Draw(lay)
    x0 = CX - w / 2
    g.rounded_rectangle((x0, 0, x0 + w, 100), 22, fill=(28, 12, 8, 200), outline=(214, 172, 92, 210), width=2)
    ctext(g, 6, l1, f1, GOLD, CX)
    ctext(g, 56, l2, f2, (252, 246, 236), CX)
    return lay


def main():
    script = json.load(open(sys.argv[1], encoding="utf-8"))
    timing = json.load(open(sys.argv[2]))
    out = sys.argv[3]
    scenes, total = plan(script, timing)
    json.dump({"scenes": [{k: v for k, v in s.items() if k != "line"} | {"scene": s["line"]["scene"]} for s in scenes], "total": total},
              open(os.path.splitext(out)[0] + ".plan.json", "w"), indent=1)
    if "--still" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--still") + 1:]]
        for t in ts:
            frame(script, scenes, t).save(f"{os.path.splitext(out)[0]}_{t:05.2f}.jpg", quality=90)
        return
    tmp = out + ".tmp.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    n = int(round(total * FPS))
    for k in range(n):
        p.stdin.write(frame(script, scenes, k / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ffmpeg lỗi")
    os.replace(tmp, out)
    print(f"Đã dựng {out}: {total:.1f} giây", file=sys.stderr)


if __name__ == "__main__":
    main()
