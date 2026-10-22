"""Shared drawing kit for the bot's Discord image cards.

Every card uses the website's fonts, colours and battlefield artwork so Discord and
the site look like one product. Functions here only draw; the cards module lays
out each card and card_send attaches the result to a Discord message.
"""
import io
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
FONTS = WEB / 'fonts'
BADGES = ROOT / 'rank_badges'
BADGE_NAMES = ('pte', 'lcpl', 'cpl', 'sgt', 'ssgt', 'wo2', 'wo1')
UK = ZoneInfo('Europe/London')
W, PAD = 1080, 64
BG, PANEL, LINE = (18, 20, 16), (30, 33, 27), (52, 56, 46)
LIME, GOLD, RED = (166, 227, 90), (230, 196, 106), (224, 82, 92)
SILVER, BRONZE = (189, 201, 212), (205, 140, 82)
TEXT, MUTED, SOFT = (242, 240, 232), (160, 163, 150), (205, 205, 196)
SITE = '22a.up.railway.app'
_FILES = {'head': 'barlow-condensed-latin-700-normal', 'semi': 'barlow-condensed-latin-600-normal',
          'mono': 'jetbrains-mono-latin-500-normal', 'body': 'dm-sans-latin-400-normal',
          'bold': 'dm-sans-latin-700-normal', 'mid': 'dm-sans-latin-600-normal'}
_fonts, _art = {}, {}


def font(kind, size):
    key = (kind, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONTS / (_FILES[kind] + '.woff2')), size)
    return _fonts[key]


def clean(text):
    """Keep characters the Latin web fonts can draw; drop emoji and other scripts."""
    out = ''.join(c for c in str(text) if ord(c) < 0x250 or 0x2010 <= ord(c) <= 0x2026 or c in '×·•')
    return ' '.join(out.split())


def short(name):
    name = clean(name or '') or 'Member'
    return name[6:] if name.upper().startswith('[22A] ') else name


def fit(draw, text, kind, size, width, floor=18):
    """Shrink the font until the text fits, then trim with an ellipsis if still too wide."""
    text = clean(text)
    while size > floor and draw.textlength(text, font=font(kind, size)) > width:
        size -= 2
    f = font(kind, size)
    while draw.textlength(text, font=f) > width and len(text) > 1:
        text = text[:-2] + '…'
    return text, f


def spaced(draw, xy, text, f, fill, gap):
    """Letter-spaced label text; returns the x where it ends."""
    x, y = xy
    for ch in clean(text):
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + gap
    return x


def spaced_width(draw, text, f, gap):
    text = clean(text)
    return sum(draw.textlength(ch, font=f) + gap for ch in text) - gap if text else 0


def right(draw, x, y, text, f, fill):
    """Draw text with its right edge at x."""
    text = clean(text)
    draw.text((x - draw.textlength(text, font=f), y), text, font=f, fill=fill)


def hero(width, height, darkness=150):
    """The site's battlefield art, darkened and faded into the page colour at the bottom."""
    key = (width, height, darkness)
    if key not in _art:
        art = Image.open(WEB / 'battlefield-realistic.webp').convert('RGB')
        art = ImageOps.fit(art, (width, height), centering=(0.5, 0.4)).filter(ImageFilter.GaussianBlur(1.2))
        shade = Image.new('L', (1, height))
        for y in range(height):
            t = y / height
            value = darkness + (255 - darkness) * (t ** 1.6) if t > 0.15 else darkness + 60 * (0.15 - t) / 0.15
            shade.putpixel((0, y), int(min(255, value)))
        _art[key] = Image.composite(Image.new('RGB', (width, height), BG), art, shade.resize((width, height)))
    return _art[key].copy()


def picture(data, size):
    """A square portrait from image bytes, falling back to the 22A crest."""
    try:
        img = Image.open(io.BytesIO(data)).convert('RGB') if data else Image.open(WEB / 'logo.png').convert('RGB')
    except Exception:
        img = Image.open(WEB / 'logo.png').convert('RGB')
    return ImageOps.fit(img, (size, size))


def portrait(img, data, xy, size, border=LIME):
    x, y = xy
    img.paste(Image.new('RGB', (size + 8, size + 8), border), (x, y))
    img.paste(picture(data, size), (x + 4, y + 4))


def badge(rank, size):
    """The rank's badge artwork (transparent PNG), or None if missing."""
    try:
        return Image.open(BADGES / (BADGE_NAMES[rank] + '.png')).convert('RGBA').resize((size, size), Image.LANCZOS)
    except Exception:
        return None


def paste_badge(img, rank, xy, size):
    b = badge(rank, size)
    if b:
        img.paste(b, xy, b)


def brackets(draw, box, colour, arm=22, width=4):
    x0, y0, x1, y1 = box
    draw.line([(x0, y0 + arm), (x0, y0), (x0 + arm, y0)], fill=colour, width=width)
    draw.line([(x1 - arm, y1), (x1, y1), (x1, y1 - arm)], fill=colour, width=width)


def banner(img, box, colour=GOLD, strength=0.22):
    """A tinted band with corner brackets, like the 'TOP 0.4%' strip."""
    band = Image.new('RGB', (box[2] - box[0], box[3] - box[1]), colour)
    img.paste(Image.blend(img.crop(box), band, strength), box[:2])
    brackets(ImageDraw.Draw(img), (box[0] - 2, box[1] - 4, box[2] + 2, box[3] + 4), colour)


def tile(draw, box, label, value, sub, accent=LIME):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL, outline=LINE)
    draw.rectangle((x0, y0, x0 + 5, y1), fill=accent)
    spaced(draw, (x0 + 28, y0 + 22), label, font('mono', 20), MUTED, 5)
    text, f = fit(draw, value, 'head', 58, x1 - x0 - 56)
    draw.text((x0 + 28, y0 + 52), text, font=f, fill=TEXT)
    text, f = fit(draw, sub, 'body', 22, x1 - x0 - 56, 14)
    draw.text((x0 + 28, y1 - 38), text, font=f, fill=MUTED)


def tiles(draw, y, items, accent=LIME):
    """Two-column grid of tiles; returns the y below it."""
    half = (W - 2 * PAD - 24) // 2
    for i, item in enumerate(items):
        x = PAD + (i % 2) * (half + 24)
        top = y + (i // 2) * 176
        tile(draw, (x, top, x + half, top + 158), *item[:3], accent=item[3] if len(item) > 3 else accent)
    return y + ((len(items) + 1) // 2) * 176


def numbers(draw, y, stats):
    """The row of big numbers with spaced labels; returns the y below it."""
    col = (W - 2 * PAD) / len(stats)
    size = 88 if len(stats) <= 4 else 72
    for i, (value, label) in enumerate(stats):
        x = PAD + i * col
        if i:
            draw.line([(x - 20, y + 10), (x - 20, y + 120)], fill=LINE, width=2)
        text, f = fit(draw, value, 'head', size, col - 30, 40)
        draw.text((x, y), text, font=f, fill=TEXT)
        spaced(draw, (x + 4, y + 98), label, font('mono', 22), MUTED, 6)
    return y + 150


def bar(draw, box, fraction, colour=LIME):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=LINE)
    if fraction > 0:
        draw.rectangle((x0, y0, x0 + int((x1 - x0) * min(1, fraction)), y1), fill=colour)


def versus(draw, y, left, right_side):
    """Nemesis-style row: left = (label, name, sub, colour), right likewise. Either may be None."""
    half = (W - 2 * PAD - 24) // 2
    draw.rectangle((PAD, y, W - PAD, y + 110), fill=PANEL, outline=LINE)
    if left:
        label, name, sub, colour = left
        spaced(draw, (PAD + 32, y + 18), label, font('mono', 22), colour, 8)
        text, f = fit(draw, name, 'bold', 34, half - 120)
        draw.text((PAD + 32, y + 44), text, font=f, fill=TEXT)
        draw.text((PAD + 32, y + 84), clean(sub), font=font('body', 20), fill=MUTED)
    if right_side:
        label, name, sub, colour = right_side
        lw = spaced_width(draw, label, font('mono', 22), 8)
        spaced(draw, (W - PAD - 32 - lw, y + 18), label, font('mono', 22), colour, 8)
        text, f = fit(draw, name, 'bold', 34, half - 120)
        right(draw, W - PAD - 32, y + 44, text, f, TEXT)
        right(draw, W - PAD - 32, y + 84, sub, font('body', 20), MUTED)
    if left and right_side:
        vw = draw.textlength('VS', font=font('head', 40)) + 28
        draw.rectangle((W / 2 - vw / 2, y + 32, W / 2 + vw / 2, y + 80), fill=(14, 15, 12))
        draw.text((W / 2 - vw / 2 + 14, y + 33), 'VS', font=font('head', 40), fill=GOLD)
    return y + 110


def header(img, draw, kicker, tail, accent=LIME, crest=True):
    """Top accent bar, the letter-spaced kicker line and the 22A crest."""
    draw.rectangle((0, 0, img.width, 9), fill=accent)
    x = spaced(draw, (PAD, 58), kicker, font('mono', 26), accent, 9)
    if tail:
        spaced(draw, (x + 14, 58), '·  ' + tail, font('mono', 26), TEXT, 9)
    if crest:
        img.paste(picture(None, 92), (img.width - PAD - 92, 40))


def footer(draw, height, left_text, width=W):
    y = height - 62
    draw.text((PAD, y), clean(left_text), font=font('body', 24), fill=MUTED)
    right(draw, width - PAD, y - 2, SITE, font('bold', 26), TEXT)


def arrow(draw, x, y, length, colour, width=6):
    """A right-pointing arrow (the web fonts have no arrow glyph)."""
    head = width * 3
    draw.line([(x, y), (x + length - head, y)], fill=colour, width=width)
    draw.polygon([(x + length - head, y - head), (x + length, y), (x + length - head, y + head)], fill=colour)


def png(img):
    out = io.BytesIO()
    img.save(out, 'PNG', compress_level=6)
    return out.getvalue()
