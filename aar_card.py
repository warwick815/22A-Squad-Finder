"""Draws the squad after-action report as a shareable image card for Discord.

Pure drawing: takes a closed session (see kill_feed._close_session) and returns PNG
bytes. Uses the website's own fonts and battlefield artwork so the card matches the site.
"""
import io
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

WEB = Path(__file__).resolve().parent / 'web'
FONTS = WEB / 'fonts'
UK = ZoneInfo('Europe/London')
W, PAD = 1080, 64
BG, PANEL, LINE = (18, 20, 16), (30, 33, 27), (52, 56, 46)
LIME, GOLD, RED = (166, 227, 90), (230, 196, 106), (224, 82, 92)
TEXT, MUTED = (242, 240, 232), (160, 163, 150)
SITE = '22a.up.railway.app'
_fonts = {}


def font(kind, size):
    files = {'head': 'barlow-condensed-latin-700-normal', 'semi': 'barlow-condensed-latin-600-normal',
             'mono': 'jetbrains-mono-latin-500-normal', 'body': 'dm-sans-latin-400-normal',
             'bold': 'dm-sans-latin-700-normal', 'mid': 'dm-sans-latin-600-normal'}
    key = (kind, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONTS / (files[kind] + '.woff2')), size)
    return _fonts[key]


def short(name):
    name = str(name or 'Unknown')
    return name[6:] if name.upper().startswith('[22A] ') else name


def clean(text):
    # The web fonts only carry Latin glyphs; anything else would draw as boxes.
    return ''.join(c if ord(c) < 0x250 else '?' for c in str(text))


def fit(draw, text, kind, size, width, floor=18):
    text = clean(text)
    while size > floor and draw.textlength(text, font=font(kind, size)) > width:
        size -= 2
    f = font(kind, size)
    while draw.textlength(text, font=f) > width and len(text) > 1:
        text = text[:-2] + '…'
    return text, f


def spaced(draw, xy, text, f, fill, gap):
    x, y = xy
    for ch in clean(text):
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + gap
    return x


def spaced_width(draw, text, f, gap):
    return sum(draw.textlength(ch, font=f) + gap for ch in text) - gap


def headline(e):
    """The one-word verdict on the session, like a Wrapped title."""
    kills, hs = e['kills'], e.get('headshots', 0)
    minutes = max(1, (e['end'] - e['start']) / 60)
    deaths = e.get('deaths', 0)
    longest = (e.get('longest') or {}).get('m') or 0
    n = len(e['members'])
    if kills >= 10 and hs / kills >= 0.4:
        return 'HEADHUNTERS', f'{round(100 * hs / kills)}% of kills were headshots'
    if longest >= 400:
        return 'SHARPSHOOTERS', f'a {longest:.0f} m kill on the board'
    if kills >= 15 and deaths and kills / deaths >= 3:
        return 'UNTOUCHABLE', f'{kills / deaths:.1f} kills for every death'
    if kills / minutes >= 1:
        return 'BLITZKRIEG', f'{kills / minutes:.1f} kills a minute'
    if n >= 6:
        return 'FULL PLATOON', f'{n} WarDogs in the field together'
    if e.get('streak') and e['streak']['count'] >= 8:
        return 'RELENTLESS', f"a {e['streak']['count']}-kill streak without dying"
    return 'THE PACK', f'{kills} kills stacked up together'


def _hero(height):
    art = Image.open(WEB / 'battlefield-realistic.webp').convert('RGB')
    art = ImageOps.fit(art, (W, height), centering=(0.5, 0.4))
    art = art.filter(ImageFilter.GaussianBlur(1.2))
    shade = Image.new('L', (1, height))
    for y in range(height):
        # Dark at the top for the header, fading fully into the page at the bottom.
        t = y / height
        shade.putpixel((0, y), int(150 + 105 * (t ** 1.6)) if t > 0.15 else int(150 + 60 * (0.15 - t) / 0.15))
    shade = shade.resize((W, height))
    return Image.composite(Image.new('RGB', (W, height), BG), art, shade)


def _avatar(data, size):
    try:
        img = Image.open(io.BytesIO(data)).convert('RGB') if data else Image.open(WEB / 'logo.png').convert('RGB')
    except Exception:
        img = Image.open(WEB / 'logo.png').convert('RGB')
    return ImageOps.fit(img, (size, size))


def _brackets(draw, box, colour, arm=22, width=4):
    x0, y0, x1, y1 = box
    draw.line([(x0, y0 + arm), (x0, y0), (x0 + arm, y0)], fill=colour, width=width)
    draw.line([(x1 - arm, y1), (x1, y1), (x1, y1 - arm)], fill=colour, width=width)


def _tile(draw, box, label, value, sub, accent=LIME):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=PANEL, outline=LINE)
    draw.rectangle((x0, y0, x0 + 5, y1), fill=accent)
    spaced(draw, (x0 + 28, y0 + 22), label, font('mono', 20), MUTED, 5)
    text, f = fit(draw, value, 'head', 58, x1 - x0 - 56)
    draw.text((x0 + 28, y0 + 52), text, font=f, fill=TEXT)
    text, f = fit(draw, sub, 'body', 22, x1 - x0 - 56, 14)
    draw.text((x0 + 28, y1 - 38), text, font=f, fill=MUTED)


def render(e, avatar=None):
    members = e['members'][:8]
    rows = (len(members) + 1) // 2
    vs = e.get('nemesis') or e.get('target')
    height = 1272 + 70 + rows * 58 + (130 if vs else 0) + 70
    img = Image.new('RGB', (W, height), BG)
    img.paste(_hero(720), (0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 9), fill=LIME)

    # Header.
    when = datetime.fromtimestamp(e['end'], UK)
    x = spaced(draw, (PAD, 58), '22A AFTER-ACTION', font('mono', 26), LIME, 9)
    spaced(draw, (x + 6, 58), ' · ' + str(e.get('server') or 'TF21').upper(), font('mono', 26), TEXT, 9)
    if avatar:  # Otherwise the portrait box already shows the 22A crest.
        img.paste(_avatar(None, 92), (W - PAD - 92, 40))

    # Top gun's portrait and the map.
    top = e['top']
    img.paste(Image.new('RGB', (158, 158), LIME), (PAD, 136))
    img.paste(_avatar(avatar, 150), (PAD + 4, 140))
    tx = PAD + 158 + 30
    text, f = fit(draw, e.get('map') or 'TF21 server', 'mid', 66, W - tx - PAD)
    draw.text((tx, 150), text, font=f, fill=TEXT)
    minutes = max(1, round((e['end'] - e['start']) / 60))
    sub = f"{str(e.get('server') or '').upper()} · {minutes} min · {when.strftime('%a %-d %b, %H:%M')}"
    text, f = fit(draw, sub, 'body', 30, W - tx - PAD)
    draw.text((tx, 238), text, font=f, fill=MUTED)

    # The verdict.
    title, why = headline(e)
    spaced(draw, (PAD, 340), 'THIS SESSION THE SQUAD WERE', font('mono', 26), (205, 205, 196), 8)
    text, f = fit(draw, title, 'head', 150, W - 2 * PAD)
    draw.text((PAD, 372), text, font=f, fill=LIME)
    x = PAD
    draw.text((x, 540), clean(why), font=font('mid', 32), fill=TEXT)
    x += draw.textlength(clean(why), font=font('mid', 32))
    tail = f"  · {len(e['members'])} members on {str(e.get('server') or 'TF21').upper()}"
    if x + draw.textlength(tail, font=font('mid', 32)) < W - PAD:
        draw.text((x, 540), tail, font=font('mid', 32), fill=GOLD)

    # Top gun banner.
    box = (PAD, 600, W - PAD, 712)
    band = Image.new('RGB', (box[2] - box[0], box[3] - box[1]), GOLD)
    img.paste(Image.blend(img.crop(box), band, 0.22), box[:2])
    _brackets(draw, (box[0] - 2, box[1] - 4, box[2] + 2, box[3] + 4), GOLD)
    big = f"{top['kills']} KILLS"
    draw.text((PAD + 30, 618), big, font=font('head', 82), fill=GOLD)
    bx = PAD + 30 + draw.textlength(big, font=font('head', 82)) + 34
    text, f = fit(draw, f"{top['name']} topped the squad", 'mid', 32, W - PAD - bx - 20)
    draw.text((bx, 625), text, font=f, fill=TEXT)
    deaths = next((m.get('deaths', 0) for m in e['members'] if m['steam'] == top['steam']), 0)
    detail = f"{top.get('headshots', 0)} headshots" + (f" · {top['kills'] / deaths:.1f} K/D" if deaths else ' · never went down')
    draw.text((bx, 668), detail, font=font('body', 26), fill=MUTED)

    # Big numbers.
    squad_deaths = e.get('deaths', 0)
    stats = [(str(len(e['members'])), 'MEMBERS'), (f"{e['kills']:,}", 'KILLS'), (str(minutes), 'MINUTES'),
             ((f"{e['kills'] / squad_deaths:.2f}", 'SQUAD K/D') if squad_deaths else (str(e.get('headshots', 0)), 'HEADSHOTS'))]
    col = (W - 2 * PAD) / 4
    for i, (value, label) in enumerate(stats):
        x = PAD + i * col
        if i:
            draw.line([(x - 20, 752), (x - 20, 862)], fill=LINE, width=2)
        draw.text((x, 742), value, font=font('head', 88), fill=TEXT)
        spaced(draw, (x + 4, 840), label, font('mono', 24), MUTED, 7)

    # Highlight tiles.
    half = (W - 2 * PAD - 24) // 2
    lng, wpn, st = e.get('longest'), e.get('weapon'), e.get('streak')
    hs = e.get('headshots', 0)
    tiles = [('LONGEST SHOT', f"{lng['m']:.0f}m" if lng else '—', f"{lng['weapon']} · {short(lng['name'])}" if lng else 'no distance recorded'),
             ('WEAPON OF CHOICE', wpn[0] if wpn else '—', f'{wpn[1]} kills this session' if wpn else ''),
             ('BEST STREAK', f"{st['count']} kills" if st else '—', f"{short(st['name'])} without dying" if st else ''),
             ('HEADSHOTS', str(hs), f"{round(100 * hs / e['kills']) if e['kills'] else 0}% of the squad's kills")]
    for i, (label, value, sub) in enumerate(tiles):
        x = PAD + (i % 2) * (half + 24)
        y = 905 + (i // 2) * 176
        _tile(draw, (x, y, x + half, y + 158), label, value, sub)

    # The squad.
    y = 1272
    spaced(draw, (PAD, y), 'THE SQUAD', font('mono', 24), LIME, 8)
    y += 50
    best = max(m['kills'] for m in members) or 1
    for i, m in enumerate(members):
        x = PAD + (i % 2) * (half + 24)
        ry = y + (i // 2) * 58
        name, f = fit(draw, short(m['name']), 'mid', 28, half - 150)
        draw.text((x, ry), name, font=f, fill=TEXT if m['steam'] != top['steam'] else GOLD)
        score = f"{m['kills']}" + (f" / {m['deaths']}" if m.get('deaths') else '')
        draw.text((x + half - draw.textlength(score, font=font('head', 34)), ry - 4), score, font=font('head', 34), fill=TEXT)
        draw.rectangle((x, ry + 40, x + half, ry + 44), fill=LINE)
        draw.rectangle((x, ry + 40, x + int(half * m['kills'] / best), ry + 44), fill=LIME)
    y += rows * 58 + 20

    # Nemesis versus favourite target.
    if vs:
        box = (PAD, y, W - PAD, y + 110)
        draw.rectangle(box, fill=PANEL, outline=LINE)
        if e.get('nemesis'):
            spaced(draw, (PAD + 32, y + 18), 'NEMESIS', font('mono', 22), RED, 8)
            name, f = fit(draw, e['nemesis']['name'], 'bold', 34, half - 120)
            draw.text((PAD + 32, y + 44), name, font=f, fill=TEXT)
            draw.text((PAD + 32, y + 84), f"killed the squad {e['nemesis']['count']}×", font=font('body', 20), fill=MUTED)
        if e.get('target'):
            label = 'FAVOURITE TARGET'
            lw = spaced_width(draw, label, font('mono', 22), 8)
            spaced(draw, (W - PAD - 32 - lw, y + 18), label, font('mono', 22), LIME, 8)
            name, f = fit(draw, e['target']['name'], 'bold', 34, half - 120)
            draw.text((W - PAD - 32 - draw.textlength(name, font=f), y + 44), name, font=f, fill=TEXT)
            sub = f"the squad got them {e['target']['count']}×"
            draw.text((W - PAD - 32 - draw.textlength(sub, font=font('body', 20)), y + 84), sub, font=font('body', 20), fill=MUTED)
        if e.get('nemesis') and e.get('target'):
            vw = draw.textlength('VS', font=font('head', 40)) + 28
            draw.rectangle((W / 2 - vw / 2, y + 32, W / 2 + vw / 2, y + 80), fill=(14, 15, 12))
            draw.text((W / 2 - vw / 2 + 14, y + 33), 'VS', font=font('head', 40), fill=GOLD)
        y += 110

    # Footer.
    y = height - 62
    draw.text((PAD, y), f"TF21 servers · {when.strftime('%-d %B %Y')}", font=font('body', 24), fill=MUTED)
    draw.text((W - PAD - draw.textlength(SITE, font=font('bold', 26)), y - 2), SITE, font=font('bold', 26), fill=TEXT)

    out = io.BytesIO()
    img.save(out, 'PNG', optimize=True)
    return out.getvalue()
