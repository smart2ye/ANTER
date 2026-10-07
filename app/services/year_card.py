"""مُولّد بطاقة الحصاد السنوي — PNG بأبعاد 1080×1920 (Story).

يستخدم Pillow + Cairo font (يعالج RTL تلقائيًا).
"""
from __future__ import annotations

import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


# ألوان ANTER
NAVY = (3, 30, 100)       # #031E64
BLUE = (0, 58, 171)       # #003AAB
CYAN = (0, 200, 248)      # #00C8F8
PURPLE = (22, 11, 142)    # #160B8E
WHITE = (255, 255, 255)
LIGHT = (220, 230, 255)
MUTED = (160, 180, 220)

W, H = 1080, 1920

_FONT_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts')


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(_FONT_DIR, name)
    return ImageFont.truetype(path, size)


def _ar(text: str) -> str:
    """Cairo font يعالج RTL مباشرة — لا حاجة لمعالجة."""
    return text or ''


def _strip_nontext(text: str) -> str:
    """يُزيل الإيموجي والرموز غير المدعومة في Cairo."""
    out = []
    for ch in (text or ''):
        cp = ord(ch)
        # نُبقي: ASCII، العربية، علامات الترقيم العربية، الرموز الشائعة.
        if (
            0x20 <= cp <= 0x7E
            or 0x0600 <= cp <= 0x06FF
            or 0x0750 <= cp <= 0x077F
            or 0xFB50 <= cp <= 0xFDFF
            or 0xFE70 <= cp <= 0xFEFF
            or cp in (0x060C, 0x061B, 0x061F, 0x066A, 0x066B, 0x066C, 0x00AB, 0x00BB, 0x2018, 0x2019, 0x201C, 0x201D, 0x2013, 0x2014, 0x2026)
        ):
            out.append(ch)
    return ''.join(out).strip() 


_LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logo.png')


def _paste_logo(img: Image.Image, center_x: int, center_y: int, size: int):
    """يُلصق شعار ANTER في وسط أفقي عند موضع معيّن."""
    try:
        logo = Image.open(_LOGO_PATH).convert('RGBA')
        logo = logo.resize((size, size), Image.LANCZOS)
        img.paste(logo, (center_x - size // 2, center_y - size // 2), logo)
    except Exception:
        pass  # لو فشل، نتجاهل بهدوء


def _gradient_bg() -> Image.Image:
    """خلفية تدرّج عمودي: navy → blue → cyan."""
    img = Image.new('RGB', (W, H), NAVY)
    px = img.load()
    stops = [
        (0.0, NAVY),
        (0.45, BLUE),
        (0.85, PURPLE),
        (1.0, NAVY),
    ]
    for y in range(H):
        t = y / (H - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                k = (t - t0) / max(t1 - t0, 1e-6)
                r = int(c0[0] + (c1[0] - c0[0]) * k)
                g = int(c0[1] + (c1[1] - c0[1]) * k)
                b = int(c0[2] + (c1[2] - c0[2]) * k)
                for x in range(W):
                    px[x, y] = (r, g, b)
                break
    return img


def _center(draw, y, text, font, fill):
    draw.text((W // 2, y), _ar(text), font=font, fill=fill, anchor='mm')


def _rounded(draw, box, radius, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render(payload: dict) -> bytes:
    """يُرجع بايتات PNG جاهزة للإرسال."""
    ui = payload['user_info']
    stats = payload['stats']
    year = payload['year']

    img = _gradient_bg()
    draw = ImageDraw.Draw(img, 'RGBA')

    f_title   = _font('Cairo.ttf', 66)
    f_year    = _font('Cairo.ttf', 130)
    f_name    = _font('Cairo.ttf', 88)
    f_user    = _font('Cairo.ttf', 46)
    f_statnum = _font('Cairo.ttf', 96)
    f_statlab = _font('Cairo.ttf', 38)
    f_body    = _font('Cairo.ttf', 46)
    f_small   = _font('Cairo.ttf', 34)
    f_foot    = _font('Cairo.ttf', 32)

    # ============ الشعار ============
    _paste_logo(img, W // 2, 130, 140)

    # ============ الترويسة ============
    _center(draw, 260, 'حصادك على', f_title, LIGHT)
    _center(draw, 395, f'ANTER {year}', f_year, CYAN)

    # خط فاصل
    draw.line([(W // 2 - 120, 500), (W // 2 + 120, 500)], fill=CYAN, width=4)

    # ============ الاسم ============
    name = ui['name']
    _center(draw, 610, name, f_name, WHITE)

    if ui.get('is_verified'):
        # شارة التوثيق — تُحسب بعد نهاية الاسم الفعلي
        name_width = draw.textlength(_ar(name), font=f_name)
        badge_x = W // 2 + name_width // 2 + 40
        badge_y = 610
        r = 30
        draw.ellipse((badge_x - r, badge_y - r, badge_x + r, badge_y + r), fill=CYAN)
        # علامة صح
        draw.line(
            [(badge_x - 14, badge_y + 2), (badge_x - 2, badge_y + 14), (badge_x + 16, badge_y - 12)],
            fill=NAVY, width=7, joint='curve'
        )

    _center(draw, 700, f"@{ui['username']}", f_user, MUTED)

    # ============ الإحصائيات (شبكة 2×2) ============
    grid_top = 800
    cell_w, cell_h = 400, 220
    gap = 40
    left_x = (W - (cell_w * 2 + gap)) // 2

    cells = [
        ('منشور', stats['total_posts']),
        ('إعجاب', stats['likes_received']),
        ('تعليق', stats['comments_received']),
        ('متابع', stats['followers']),
    ]
    for i, (label, val) in enumerate(cells):
        row, col = divmod(i, 2)
        x = left_x + col * (cell_w + gap)
        y = grid_top + row * (cell_h + gap)
        _rounded(draw, (x, y, x + cell_w, y + cell_h), radius=32,
                 fill=(255, 255, 255, 22), outline=CYAN, width=3)
        _center_in_box(draw, x, y, cell_w, cell_h, str(val), label,
                       f_statnum, f_statlab)

    # ============ أفضل منشور ============
    y_top_post = 1370
    _center(draw, y_top_post, 'أبرز منشور', f_body, CYAN)

    top_post = payload.get('top_post')
    if top_post and top_post.get('content'):
        content = _strip_nontext(top_post['content']).strip()
        content = _wrap_text(draw, f'«{content}»', f_small, W - 160)
        # نرسم حتى 6 أسطر كحد أقصى
        line_h = 54
        max_lines = 5
        for i, line in enumerate(content[:max_lines]):
            _center(draw, y_top_post + 70 + i * line_h, line, f_small, WHITE)
        _center(draw, y_top_post + 70 + len(content[:max_lines]) * line_h + 30,
                f"{top_post['likes']} إعجاب · {top_post['comments']} تعليق",
                f_small, MUTED)
    else:
        _center(draw, y_top_post + 80, 'لا منشورات بعد', f_small, MUTED)

    # ============ التذييل ============
    _center(draw, H - 110, 'شاهد حصادك الكامل', f_small, LIGHT)
    _center(draw, H - 60, 'anter-1.onrender.com', f_foot, CYAN)

    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _center_in_box(draw, bx, by, bw, bh, number, label, f_num, f_lab):
    cx = bx + bw // 2
    draw.text((cx, by + bh // 2 - 25), number, font=f_num, fill=WHITE, anchor='mm')
    draw.text((cx, by + bh // 2 + 55), _ar(label), font=f_lab, fill=MUTED, anchor='mm')


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    """يقسّم النص إلى أسطر بحيث لا يتجاوز كل سطر العرض المتاح."""
    words = text.split()
    lines = []
    current = ''
    for w in words:
        trial = f'{current} {w}'.strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines
