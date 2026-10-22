"""Draws the squad after-action report as a shareable image card for Discord.

Pure drawing: takes a closed session (see kill_feed._close_session) and returns PNG
bytes. Uses the website's own fonts and battlefield artwork so the card matches the site.
"""
from datetime import datetime

from PIL import Image, ImageDraw

from card_kit import (BG, GOLD, LIME, MUTED, PAD, RED, SOFT, TEXT, UK, W, banner, bar, clean, fit, font, footer,
                      header, hero, numbers, portrait, png, short, spaced, tiles, versus)


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


def render(e, avatar=None):
    members = e['members'][:8]
    rows = (len(members) + 1) // 2
    vs = e.get('nemesis') or e.get('target')
    height = 1272 + 70 + rows * 58 + (130 if vs else 0) + 70
    img = Image.new('RGB', (W, height), BG)
    img.paste(hero(W, 720), (0, 0))
    draw = ImageDraw.Draw(img)
    when = datetime.fromtimestamp(e['end'], UK)
    server = str(e.get('server') or 'TF21').upper()
    # With no avatar the portrait already shows the crest, so skip the corner one.
    header(img, draw, '22A AFTER-ACTION', server, crest=bool(avatar))

    # Top gun's portrait and the map.
    top = e['top']
    portrait(img, avatar, (PAD, 136), 150)
    tx = PAD + 158 + 30
    text, f = fit(draw, e.get('map') or 'TF21 server', 'mid', 66, W - tx - PAD)
    draw.text((tx, 150), text, font=f, fill=TEXT)
    minutes = max(1, round((e['end'] - e['start']) / 60))
    text, f = fit(draw, f"{server} · {minutes} min · {when.strftime('%a %-d %b, %H:%M')}", 'body', 30, W - tx - PAD)
    draw.text((tx, 238), text, font=f, fill=MUTED)

    # The verdict.
    title, why = headline(e)
    spaced(draw, (PAD, 340), 'THIS SESSION THE SQUAD WERE', font('mono', 26), SOFT, 8)
    text, f = fit(draw, title, 'head', 150, W - 2 * PAD)
    draw.text((PAD, 372), text, font=f, fill=LIME)
    draw.text((PAD, 540), clean(why), font=font('mid', 32), fill=TEXT)
    x = PAD + draw.textlength(clean(why), font=font('mid', 32))
    tail = f"  · {len(e['members'])} members on {server}"
    if x + draw.textlength(tail, font=font('mid', 32)) < W - PAD:
        draw.text((x, 540), tail, font=font('mid', 32), fill=GOLD)

    # Top gun banner.
    banner(img, (PAD, 600, W - PAD, 712))
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
    numbers(draw, 742, [(str(len(e['members'])), 'MEMBERS'), (f"{e['kills']:,}", 'KILLS'), (str(minutes), 'MINUTES'),
                        (f"{e['kills'] / squad_deaths:.2f}", 'SQUAD K/D') if squad_deaths else (str(e.get('headshots', 0)), 'HEADSHOTS')])

    # Highlight tiles.
    lng, wpn, st, hs = e.get('longest'), e.get('weapon'), e.get('streak'), e.get('headshots', 0)
    tiles(draw, 905, [
        ('LONGEST SHOT', f"{lng['m']:.0f}m" if lng else '—', f"{lng['weapon']} · {short(lng['name'])}" if lng else 'no distance recorded'),
        ('WEAPON OF CHOICE', wpn[0] if wpn else '—', f'{wpn[1]} kills this session' if wpn else ''),
        ('BEST STREAK', f"{st['count']} kills" if st else '—', f"{short(st['name'])} without dying" if st else ''),
        ('HEADSHOTS', str(hs), f"{round(100 * hs / e['kills']) if e['kills'] else 0}% of the squad's kills")])

    # The squad.
    half = (W - 2 * PAD - 24) // 2
    y = 1272
    spaced(draw, (PAD, y), 'THE SQUAD', font('mono', 24), LIME, 8)
    y += 50
    best = max(m['kills'] for m in members) or 1
    for i, m in enumerate(members):
        x = PAD + (i % 2) * (half + 24)
        ry = y + (i // 2) * 58
        name, f = fit(draw, short(m['name']), 'mid', 28, half - 150)
        draw.text((x, ry), name, font=f, fill=GOLD if m['steam'] == top['steam'] else TEXT)
        score = f"{m['kills']}" + (f" / {m['deaths']}" if m.get('deaths') else '')
        draw.text((x + half - draw.textlength(score, font=font('head', 34)), ry - 4), score, font=font('head', 34), fill=TEXT)
        bar(draw, (x, ry + 40, x + half, ry + 44), m['kills'] / best)
    y += rows * 58 + 20

    if vs:
        n, t = e.get('nemesis'), e.get('target')
        versus(draw, y, n and ('NEMESIS', n['name'], f"killed the squad {n['count']}×", RED),
               t and ('FAVOURITE TARGET', t['name'], f"the squad got them {t['count']}×", LIME))

    footer(draw, height, f"TF21 servers · {when.strftime('%-d %B %Y')}")
    return png(img)
