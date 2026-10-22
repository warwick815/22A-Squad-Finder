"""Most Wanted playing cards, styled after the 2003 deck: corner rank and suit, a
portrait panel, the target's name and their record. Every bounty week gets its own
card; a year's deck holds 54 (52 weeks, a Black Joker for week 53 and a Red Joker for
the year's top bounty hunter)."""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from card_kit import WEB, clean, fit, font, picture, png, short

W, H = 750, 1050
SCALE = 2  # Drawn at double size, then reduced, for smooth edges.
PAPER, INK, RED_INK = (244, 240, 228), (24, 24, 22), (178, 28, 38)
FADED, STAMP_RED, STAMP_GREY = (120, 116, 104), (196, 36, 44), (110, 108, 100)
RANKS = ('A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2')
SUITS = ('spades', 'clubs', 'hearts', 'diamonds')
NAMES = {'A': 'Ace', 'K': 'King', 'Q': 'Queen', 'J': 'Jack'}


def face(n):
    """(rank, suit) for card n of the deck: 1 = A♠, 2 = A♣ … 52 = 2♦, 53/54 = jokers."""
    if n == 53:
        return 'JOKER', 'black'
    if n == 54:
        return 'JOKER', 'red'
    return RANKS[(n - 1) // 4], SUITS[(n - 1) % 4]


def label(n):
    rank, suit = face(n)
    if rank == 'JOKER':
        return f'{suit.title()} Joker'
    return f'{NAMES.get(rank, rank)} of {suit.title()}'


def red(suit):
    return suit in ('hearts', 'diamonds', 'red')


def suit_shape(suit, size, colour):
    """A suit symbol as a transparent image (the web fonts have no suit glyphs)."""
    s = size * 4
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r = s / 2, s * 0.25
    if suit == 'diamonds':
        d.polygon([(c, 0), (s * 0.86, c), (c, s), (s * 0.14, c)], fill=colour)
    elif suit == 'hearts':
        d.ellipse((c - 2 * r, s * 0.08, c, s * 0.08 + 2 * r), fill=colour)
        d.ellipse((c, s * 0.08, c + 2 * r, s * 0.08 + 2 * r), fill=colour)
        d.polygon([(c - 2 * r + 2, s * 0.08 + r * 1.25), (c + 2 * r - 2, s * 0.08 + r * 1.25), (c, s * 0.95)], fill=colour)
    elif suit == 'spades':
        top = s * 0.72
        d.ellipse((c - 2 * r, top - 2 * r, c, top), fill=colour)
        d.ellipse((c, top - 2 * r, c + 2 * r, top), fill=colour)
        d.polygon([(c - 2 * r + 2, top - r * 1.25), (c + 2 * r - 2, top - r * 1.25), (c, s * 0.02)], fill=colour)
        d.polygon([(c, s * 0.6), (c - s * 0.2, s), (c + s * 0.2, s)], fill=colour)
    elif suit == 'clubs':
        cr = s * 0.21
        for x, y in ((c, s * 0.27), (c - s * 0.25, s * 0.55), (c + s * 0.25, s * 0.55)):
            d.ellipse((x - cr, y - cr, x + cr, y + cr), fill=colour)
        d.ellipse((c - cr * 0.8, s * 0.42 - cr * 0.8, c + cr * 0.8, s * 0.42 + cr * 0.8), fill=colour)
        d.polygon([(c, s * 0.45), (c - s * 0.18, s), (c + s * 0.18, s)], fill=colour)
    else:  # Joker star.
        import math
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rad = c if i % 2 == 0 else c * 0.42
            pts.append((c + rad * math.cos(a), c + rad * math.sin(a)))
        d.polygon(pts, fill=colour)
    return img.resize((size, size), Image.LANCZOS)


def _corner(card, rank, suit, colour):
    """The rank and suit in the top-left corner, drawn on its own layer so it can be rotated."""
    layer = Image.new('RGBA', (150 * SCALE, 300 * SCALE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if rank == 'JOKER':
        for i, ch in enumerate('JOKER'):
            f = font('head', 44 * SCALE)
            d.text((75 * SCALE - d.textlength(ch, font=f) / 2, (6 + i * 40) * SCALE), ch, font=f, fill=colour)
        sym = suit_shape('star', 48 * SCALE, colour)
        layer.paste(sym, (51 * SCALE, 214 * SCALE), sym)
    else:
        f = font('head', 104 * SCALE)
        d.text((75 * SCALE - d.textlength(rank, font=f) / 2, 0), rank, font=f, fill=colour)
        sym = suit_shape(suit, 64 * SCALE, colour)
        layer.paste(sym, (43 * SCALE, 122 * SCALE), sym)
    card.paste(layer, (20 * SCALE, 26 * SCALE), layer)
    flipped = layer.rotate(180)
    card.paste(flipped, ((W - 170) * SCALE, (H - 326) * SCALE), flipped)


def _portrait(photo, box):
    """Grainy black-and-white panel: the member's picture, or a silhouette in the crosshairs."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if photo is not None:
        img = ImageOps.fit(picture(photo, max(w, h)), (w, h)).convert('L')
    else:
        art = Image.open(WEB / 'battlefield-realistic.webp').convert('L')
        img = ImageOps.fit(art, (w, h), centering=(0.62, 0.45)).filter(ImageFilter.GaussianBlur(3))
        img = Image.eval(img, lambda v: int(70 + v * 0.55))
        d = ImageDraw.Draw(img)
        cx = w // 2
        # Head and shoulders.
        d.ellipse((cx - w * 0.17, h * 0.2, cx + w * 0.17, h * 0.2 + w * 0.4), fill=28)
        d.rounded_rectangle((cx - w * 0.38, h * 0.2 + w * 0.42, cx + w * 0.38, h * 1.2), radius=int(w * 0.18), fill=28)
    img = ImageOps.autocontrast(img, cutoff=2)
    noise = Image.effect_noise((w, h), 26).convert('L')
    img = Image.blend(img, noise, 0.08)
    return img.convert('RGB')


def _crosshair(d, box, colour):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, y0 + (y1 - y0) * 0.38
    r = (x1 - x0) * 0.2
    lw = 3 * SCALE
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=lw)
    for a, b in (((cx - r * 1.5, cy), (cx - r * 0.45, cy)), ((cx + r * 0.45, cy), (cx + r * 1.5, cy)),
                 ((cx, cy - r * 1.5), (cx, cy - r * 0.45)), ((cx, cy + r * 0.45), (cx, cy + r * 1.5))):
        d.line([a, b], fill=colour, width=lw)


def _stamp(card, text, colour):
    f = font('head', 120 * SCALE)
    probe = ImageDraw.Draw(card)
    tw = int(probe.textlength(text, font=f))
    layer = Image.new('RGBA', (tw + 80 * SCALE, 190 * SCALE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle((6 * SCALE, 6 * SCALE, layer.width - 6 * SCALE, layer.height - 6 * SCALE), outline=colour + (220,), width=9 * SCALE)
    d.text((40 * SCALE, 18 * SCALE), text, font=f, fill=colour + (220,))
    layer = layer.rotate(14, expand=True, resample=Image.BICUBIC)
    card.paste(layer, ((W * SCALE - layer.width) // 2, 300 * SCALE - layer.height // 2), layer)


def render(entry, year, photo=None):
    """entry: a deck card {n, name, kills, week, status, claimed_name, weapon, distance, headshot}
    (for the Red Joker: {n: 54, name, count}). Returns PNG bytes."""
    n = int(entry['n'])
    rank, suit = face(n)
    colour = RED_INK if red(suit) else INK
    S = SCALE
    card = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, W * S - 1, H * S - 1), radius=36 * S, fill=PAPER, outline=(170, 164, 150), width=2 * S)
    d.rounded_rectangle((14 * S, 14 * S, (W - 14) * S, (H - 14) * S), radius=26 * S, outline=(205, 199, 186), width=2 * S)
    _corner(card, rank, suit, colour)

    joker_hunter = n == 54
    status = 'hunter' if joker_hunter else entry.get('status', 'open')
    heading = 'HUNTER OF THE YEAR' if joker_hunter else '22A MOST WANTED'
    f = font('mono', 22 * S)
    text = clean(f'{heading} · {year}')
    gap = 4 * S
    tw = sum(d.textlength(ch, font=f) + gap for ch in text) - gap
    x = (W * S - tw) / 2
    for ch in text:
        d.text((x, 44 * S), ch, font=f, fill=FADED)
        x += d.textlength(ch, font=f) + gap

    box = (170 * S, 96 * S, (W - 170) * S, 620 * S)
    panel = _portrait(photo, (0, 0, box[2] - box[0], box[3] - box[1]))
    card.paste(panel, box[:2])
    d.rectangle(box, outline=INK, width=4 * S)
    if status == 'open' and photo is None:
        _crosshair(d, box, STAMP_RED)

    # Name and record under the portrait, as on the original deck.
    name = short(entry.get('name')) if joker_hunter else clean(entry.get('name') or 'Unknown')
    text, f = fit(d, name.upper(), 'head', 92 * S, (W - 120) * S, 30 * S)
    d.text(((W * S - d.textlength(text, font=f)) / 2, 640 * S), text, font=f, fill=INK)
    if joker_hunter:
        line = f"{entry.get('count', 0)} bounties claimed in {year}"
    else:
        week = str(entry.get('week', '')).split('-W')[-1]
        line = f"Killed 22A members {entry.get('kills', 0)}× · Week {week}"
    text, f = fit(d, line, 'mid', 30 * S, (W - 140) * S, 14 * S)
    d.text(((W * S - d.textlength(text, font=f)) / 2, 752 * S), text, font=f, fill=FADED)
    d.line([(150 * S, 806 * S), ((W - 150) * S, 806 * S)], fill=(200, 194, 180), width=2 * S)

    if status == 'claimed':
        how = ' · '.join(x for x in (entry.get('weapon'), f"{entry['distance']:.0f} m" if entry.get('distance') is not None else None,
                                     'headshot' if entry.get('headshot') else None) if x)
        top, bottom, tint = f"CLAIMED BY {short(entry.get('claimed_name')).upper()}", how, STAMP_RED
    elif status == 'escaped':
        top, bottom, tint = 'ESCAPED', 'Nobody collected this bounty', STAMP_GREY
    elif joker_hunter:
        top, bottom, tint = 'TOP BOUNTY HUNTER', 'Wild card of the deck', RED_INK
    else:
        top, bottom, tint = 'REWARD: BOUNTY HUNTER RIBBON', 'First kill on any TF21 server claims it', RED_INK
    # Kept narrower than the card so it clears the upside-down corner index.
    text, f = fit(d, top, 'head', 46 * S, (W - 300) * S, 20 * S)
    d.text(((W * S - d.textlength(text, font=f)) / 2, 826 * S), text, font=f, fill=tint)
    text, f = fit(d, bottom, 'body', 26 * S, (W - 300) * S, 14 * S)
    d.text(((W * S - d.textlength(text, font=f)) / 2, 886 * S), text, font=f, fill=FADED)

    if status == 'claimed':
        _stamp(card, 'CLAIMED', STAMP_RED)
    elif status == 'escaped':
        _stamp(card, 'ESCAPED', STAMP_GREY)
    return png(card.resize((W, H), Image.LANCZOS))
