"""Image cards for the bot's Discord posts: profiles, comparisons, rank changes,
standings, the weekly report and bounties. Each function takes plain data and
returns PNG bytes; card_send attaches them to messages."""
from datetime import datetime

from PIL import Image, ImageDraw

from card_kit import (arrow, BG, BRONZE, GOLD, LIME, LINE, MUTED, PAD, PANEL, RED, SILVER, SOFT, TEXT, UK, W, banner, bar,
                      clean, fit, font, footer, header, hero, numbers, paste_badge, picture, portrait, png, right, short, spaced,
                      tiles, versus)

DIVISION_COLOURS = (BRONZE, SILVER, GOLD)


def _n(value, decimals=0, suffix=''):
    if type(value) not in (int, float) or value != value or value < 0:
        return '—'
    return f'{value:,.{decimals}f}{suffix}'


def _today():
    return datetime.now(UK).strftime('%-d %B %Y')


def playstyle(stats, combat):
    """A one-word verdict for a profile, like a Wrapped title."""
    stats, combat = stats or {}, combat or {}
    kills, hs = combat.get('kills') or 0, combat.get('headshots') or 0
    longest = (combat.get('longest') or {}).get('m') or 0
    streak = (combat.get('best_streak') or {}).get('count') or 0
    kd, wr, hours = stats.get('kd'), stats.get('winRate'), stats.get('hoursPlayed')
    if kills >= 50 and hs / kills >= 0.4:
        return 'HEADHUNTER', f'{round(100 * hs / kills)}% of gun kills were headshots'
    if (combat.get('bounties') or 0) >= 1:
        return 'BOUNTY HUNTER', f"{combat['bounties']} Most Wanted target{'s' if combat['bounties'] > 1 else ''} taken down"
    if longest >= 450:
        return 'SHARPSHOOTER', f'a {longest:.0f} m kill on record'
    if streak >= 15:
        return 'UNSTOPPABLE', f'{streak} kills in a row without dying'
    if type(kd) in (int, float) and kd >= 2:
        return 'APEX PREDATOR', f'{kd:.2f} kills for every death'
    if type(wr) in (int, float) and wr >= 55 and (stats.get('wins') or 0) >= 20:
        return 'MATCH WINNER', f'wins {wr:.0f}% of the matches they play'
    if type(hours) in (int, float) and hours >= 200:
        return 'LIFER', f'{hours:,.0f} hours in the field'
    return 'WARDOG', 'on the books and climbing'


def profile(d, avatar=None):
    """The member's service record, styled like the Wrapped card."""
    combat = d.get('combat') or {}
    show_vs = combat.get('nemesis') or combat.get('favourite')
    height = 1290 + (130 if show_vs else 0) + 70
    img = Image.new('RGB', (W, height), BG)
    img.paste(hero(W, 720), (0, 0))
    draw = ImageDraw.Draw(img)
    header(img, draw, '22A SERVICE RECORD', f"SEASON {d.get('season', 1)}")

    portrait(img, avatar, (PAD, 136), 150)
    tx = PAD + 158 + 30
    text, f = fit(draw, d['name'], 'mid', 66, W - tx - PAD)
    draw.text((tx, 150), text, font=f, fill=TEXT)
    sub = f"{d['rank_name']} · {d['division']['name']} division · {d.get('status') or 'Active'}"
    text, f = fit(draw, sub, 'body', 30, W - tx - PAD)
    draw.text((tx, 238), text, font=f, fill=MUTED)

    title, why = playstyle(d.get('stats'), combat)
    spaced(draw, (PAD, 340), 'IN THE FIELD THEY ARE A', font('mono', 26), SOFT, 8)
    text, f = fit(draw, title, 'head', 150, W - 2 * PAD)
    draw.text((PAD, 372), text, font=f, fill=LIME)
    text, f = fit(draw, why, 'mid', 32, W - 2 * PAD)
    draw.text((PAD, 540), text, font=f, fill=TEXT)

    # ELO banner with the rank badge and progress to the next rank.
    banner(img, (PAD, 600, W - PAD, 712))
    paste_badge(img, d['rank'], (PAD + 22, 610), 92)
    big = f"{d['rating']:,.0f} ELO"
    draw.text((PAD + 134, 618), big, font=font('head', 82), fill=GOLD)
    bx = PAD + 134 + draw.textlength(big, font=font('head', 82)) + 30
    place = f"#{d['position']} of {d['members']} members" if d.get('position') else 'Season standings'
    if d.get('skill'):
        place += f" · combat {d['skill']['rating']:,} (x{d['skill']['multiplier']:.2f})"
    text, f = fit(draw, place, 'mid', 30, W - PAD - bx - 24)
    draw.text((bx, 616), text, font=f, fill=TEXT)
    nxt = d.get('next_rank')
    if nxt:
        span = max(1, nxt['points'] - d['floor'])
        text, f = fit(draw, f"{max(0, nxt['points'] - d['rating']):,.0f} points to {nxt['name']}", 'body', 22, W - PAD - bx - 24, 14)
        draw.text((bx, 656), text, font=f, fill=MUTED)
        bar(draw, (bx, 692, W - PAD - 24, 698), (d['rating'] - d['floor']) / span, GOLD)
    else:
        draw.text((bx, 668), 'Highest rank achieved', font=font('body', 26), fill=MUTED)

    s = d.get('stats') or {}
    numbers(draw, 742, [(_n(s.get('hoursPlayed')), 'HOURS'), (_n(s.get('wins')), 'WINS'),
                        (_n(s.get('kills')), 'KILLS'), (_n(s.get('kd'), 2), 'K/D')])

    lng, streak, top = combat.get('longest'), combat.get('best_streak'), d.get('top_weapon')
    wins, losses = s.get('wins'), s.get('losses')
    tiles(draw, 905, [
        ('LONGEST KILL', f"{lng['m']:.0f}m" if lng else '—', f"{lng['weapon']} on {short(lng.get('victim'))}" if lng else 'from the TF21 kill feed'),
        ('TOP GUN', top['weapon'] if top else '—',
         f"{top['kills']:,} kills · {round(100 * top['headshots'] / top['kills']) if top['kills'] else 0}% headshots" if top else 'needs 10 kills with one weapon'),
        ('BEST STREAK', f"{streak['count']} kills" if streak else '—', f"mostly the {streak['weapon']}" if streak else 'kills between deaths'),
        ('WIN RATE', _n(s.get('winRate'), 0, '%'), f'{_n(wins)} won · {_n(losses)} lost')])

    y = 1270
    if show_vs:
        n, t = combat.get('nemesis'), combat.get('favourite')
        versus(draw, y, n and ('NEMESIS', n['name'], f"killed them {n['count']}×", RED),
               t and ('FAVOURITE TARGET', t['name'], f"they got them {t['count']}×", LIME))
    footer(draw, height, d.get('footer') or f'Snapshot {_today()} · WDUK + TF21')
    return png(img)


def compare(d, avatars=(None, None)):
    """Head-to-head: d = {'left': side, 'right': side, 'rows': [(label, ltext, rtext, lnum, rnum, lower_is_better)]}."""
    rows = d['rows']
    height = 520 + len(rows) * 64 + 90
    img = Image.new('RGB', (W, height), BG)
    img.paste(hero(W, 520), (0, 0))
    draw = ImageDraw.Draw(img)
    header(img, draw, '22A HEAD TO HEAD', None, crest=False)
    half = (W - 2 * PAD) // 2
    for i, side in enumerate((d['left'], d['right'])):
        x = PAD if i == 0 else W - PAD - 158
        portrait(img, avatars[i], (x, 140), 150, LIME if i == 0 else GOLD)
        name, f = fit(draw, short(side['name']), 'head', 64, half - 40)
        sub = f"{side['rank_name']} · {side['rating']:,.0f} ELO"
        if i == 0:
            draw.text((PAD, 320), name, font=f, fill=TEXT)
            draw.text((PAD, 400), clean(sub), font=font('body', 28), fill=MUTED)
        else:
            right(draw, W - PAD, 320, name, f, TEXT)
            right(draw, W - PAD, 400, sub, font('body', 28), MUTED)
    vw = draw.textlength('VS', font=font('head', 90))
    draw.text((W / 2 - vw / 2, 170), 'VS', font=font('head', 90), fill=GOLD)
    wins = [0, 0]
    y = 500
    for label, ltext, rtext, a, b, lower in rows:
        draw.rectangle((PAD, y, W - PAD, y + 54), fill=PANEL)
        label = clean(label).upper()
        tw = draw.textlength(label, font=font('mono', 20))
        draw.text((W / 2 - tw / 2, y + 16), label, font=font('mono', 20), fill=MUTED)
        better = None
        if type(a) in (int, float) and type(b) in (int, float) and a != b and lower is not None:
            better = 0 if (a < b if lower else a > b) else 1
            wins[better] += 1
        draw.text((PAD + 24, y + 6), clean(ltext), font=font('head', 40), fill=LIME if better == 0 else TEXT)
        right(draw, W - PAD - 24, y + 6, rtext, font('head', 40), GOLD if better == 1 else TEXT)
        y += 64
    verdict = ('Level pegging' if wins[0] == wins[1] else
               f"{short(d['left']['name'] if wins[0] > wins[1] else d['right']['name'])} leads {max(wins)}–{min(wins)}")
    text, f = fit(draw, verdict, 'mid', 30, W - 2 * PAD)
    draw.text((PAD, 450), text, font=f, fill=GOLD)
    footer(draw, height, f'Lifetime stats · {_today()}')
    return png(img)


def rank_change(d, avatar=None):
    """Promotion or demotion announcement, landscape for Discord."""
    width, height = 1200, 640
    up = d['to'] > d['from']
    accent = LIME if up else RED
    img = Image.new('RGB', (width, height), BG)
    img.paste(hero(width, height, 175), (0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width, 9), fill=accent)
    spaced(draw, (PAD, 56), '22A RANK UPDATE', font('mono', 26), accent, 9)
    img.paste(picture(None, 84), (width - PAD - 84, 36))
    portrait(img, avatar, (PAD, 130), 230, accent)
    x = PAD + 238 + 44
    spaced(draw, (x, 140), 'PROMOTED TO' if up else 'DROPPED TO', font('mono', 26), SOFT, 8)
    text, f = fit(draw, d['to_name'].upper(), 'head', 120, width - x - PAD)
    draw.text((x, 172), text, font=f, fill=accent)
    text, f = fit(draw, d['name'], 'mid', 40, width - x - PAD)
    draw.text((x, 310), text, font=f, fill=TEXT)
    # Badge journey.
    paste_badge(img, d['from'], (PAD, 420), 100)
    arrow(draw, PAD + 116, 470, 90, MUTED)
    paste_badge(img, d['to'], (PAD + 222, 420), 100)
    bx = PAD + 360
    banner(img, (bx, 420, width - PAD, 530), accent, 0.18)
    before = f"{d['before']:,.0f}"
    draw.text((bx + 28, 428), before, font=font('head', 64), fill=MUTED)
    ax = bx + 28 + draw.textlength(before, font=font('head', 64)) + 18
    arrow(draw, ax, 466, 60, accent)
    draw.text((ax + 78, 428), f"{d['after']:,.0f}", font=font('head', 64), fill=TEXT)
    delta = d.get('delta') or {}
    plural = lambda n, word: f"{n} {word}{'' if n == 1 else ('es' if word.endswith('s') else 's')}"
    line = (' · '.join([plural(delta.get('wins', 0), 'win'), plural(delta.get('losses', 0), 'loss'),
                        plural(delta.get('kills', 0), 'kill'), plural(delta.get('deaths', 0), 'death')])
            if delta else (d.get('reason') or 'Rating adjustment'))
    text, f = fit(draw, line, 'body', 24, width - bx - PAD - 56, 16)
    draw.text((bx + 28, 498), text, font=f, fill=MUTED)
    footer(draw, height, f"{'Promotion' if up else 'Demotion'} · {_today()}", width)
    return png(img)


def standings(d, avatars=()):
    """A ranked list with a podium: d = {'kicker', 'tail', 'title', 'sub', 'rows': [{name, rating, rank, rank_name, note}], 'foot'}."""
    rows = d['rows'][:20]
    rest = rows[3:]
    height = 730 + len(rest) * 62 + 90
    img = Image.new('RGB', (W, height), BG)
    img.paste(hero(W, 760), (0, 0))
    draw = ImageDraw.Draw(img)
    header(img, draw, d['kicker'], d.get('tail'))
    text, f = fit(draw, d['title'], 'head', 110, W - 2 * PAD)
    draw.text((PAD, 120), text, font=f, fill=LIME)
    text, f = fit(draw, d.get('sub') or '', 'mid', 30, W - 2 * PAD)
    draw.text((PAD, 250), text, font=f, fill=TEXT)
    # Podium: first in the middle, raised.
    slots = [(1, 360, SILVER), (0, 310, GOLD), (2, 390, BRONZE)]
    col = (W - 2 * PAD) / 3
    for n, (index, top, colour) in enumerate(slots):
        if index >= len(rows):
            continue
        r = rows[index]
        cx = int(PAD + col * n + col / 2)
        size = 170 if index == 0 else 140
        portrait(img, avatars[index] if index < len(avatars) else None, (cx - size // 2 - 4, top), size, colour)
        y = top + size + 22
        tag = f'{index + 1}'
        draw.ellipse((cx - 24, top - 24, cx + 24, top + 24), fill=colour)
        tw = draw.textlength(tag, font=font('head', 38))
        draw.text((cx - tw / 2, top - 22), tag, font=font('head', 38), fill=BG)
        name, f = fit(draw, short(r['name']), 'mid', 32, col - 20)
        draw.text((cx - draw.textlength(name, font=f) / 2, y), name, font=f, fill=TEXT)
        score = f"{r['rating']:,.0f}"
        draw.text((cx - draw.textlength(score, font=font('head', 52)) / 2, y + 40), score, font=font('head', 52), fill=colour)
        sub, f = fit(draw, r.get('rank_name', ''), 'body', 22, col - 20)
        draw.text((cx - draw.textlength(sub, font=f) / 2, y + 100), sub, font=f, fill=MUTED)
    y = 730
    best = max((r['rating'] for r in rows), default=1) or 1
    for i, r in enumerate(rest, 4):
        draw.rectangle((PAD, y, W - PAD, y + 52), fill=PANEL if i % 2 else BG)
        draw.text((PAD + 18, y + 6), f'{i}', font=font('head', 38), fill=MUTED)
        paste_badge(img, r.get('rank', 0), (PAD + 80, y + 6), 40)
        name, f = fit(draw, short(r['name']), 'mid', 28, 470)
        draw.text((PAD + 136, y + 10), name, font=f, fill=TEXT)
        if r.get('note'):
            draw.text((PAD + 136 + draw.textlength(name, font=f) + 14, y + 16), clean(r['note']), font=font('body', 20), fill=RED)
        bar(draw, (W - PAD - 330, y + 24, W - PAD - 150, y + 28), r['rating'] / best)
        right(draw, W - PAD - 18, y + 4, f"{r['rating']:,.0f}", font('head', 40), TEXT)
        y += 62
    footer(draw, height, d.get('foot') or _today())
    return png(img)


def weekly(d):
    """The weekly community report: d = {'range', 'totals', 'gains': [(name, gain)], 'promotions', 'demotions',
    'streak', 'sessions', 'bounties'}."""
    gains = d['gains'][:10]
    height = 1170 + max(1, len(gains)) * 58 + 90
    img = Image.new('RGB', (W, height), BG)
    img.paste(hero(W, 640), (0, 0))
    draw = ImageDraw.Draw(img)
    header(img, draw, '22A WEEKLY REPORT', d['range'].upper())
    t = d['totals']
    spaced(draw, (PAD, 150), 'THIS WEEK THE PACK', font('mono', 26), SOFT, 8)
    kills, deaths = t.get('kills', 0), t.get('deaths', 0)
    wins, losses = t.get('wins', 0), t.get('losses', 0)
    if wins + losses and wins / (wins + losses) >= 0.55:
        title, why = 'WON THE WEEK', f'{round(100 * wins / (wins + losses))}% of player results were wins'
    elif deaths and kills / deaths >= 1.5:
        title, why = 'RAN THE SHOW', f'{kills / deaths:.2f} kills for every death'
    elif kills >= 1000:
        title, why = 'WENT LOUD', f'{kills:,} kills across the squad'
    else:
        title, why = 'HELD THE LINE', 'results logged, ranks moved'
    text, f = fit(draw, title, 'head', 140, W - 2 * PAD)
    draw.text((PAD, 182), text, font=f, fill=LIME)
    text, f = fit(draw, why, 'mid', 32, W - 2 * PAD)
    draw.text((PAD, 340), text, font=f, fill=TEXT)
    banner(img, (PAD, 400, W - PAD, 500))
    draw.text((PAD + 30, 412), f"{d['promotions']} UP", font=font('head', 74), fill=GOLD)
    bx = PAD + 30 + draw.textlength(f"{d['promotions']} UP", font=font('head', 74)) + 34
    draw.text((bx, 420), 'promotions this week', font=font('mid', 30), fill=TEXT)
    draw.text((bx, 458), f"{d['demotions']} demotion{'s' if d['demotions'] != 1 else ''}", font=font('body', 24), fill=MUTED)
    numbers(draw, 540, [(_n(wins), 'WINS'), (_n(losses), 'LOSSES'), (_n(kills), 'KILLS'), (_n(deaths), 'DEATHS')])
    st, b = d.get('streak'), d.get('bounties') or {}
    tiles(draw, 710, [
        ('STREAK OF THE WEEK', f"{st['count']} kills" if st else '—', f"{short(st['name'])} · {st.get('weapon') or ''}" if st else 'no TF21 streaks logged'),
        ('BOUNTIES COLLECTED', f"{b['claimed']} of {b['posted']}" if b.get('posted') else '—',
         (f"top hunter {short(b['top']['name'])} · {b['top']['count']}" if b.get('top') else 'none collected yet') if b.get('posted') else 'no Most Wanted this week',
         GOLD if b.get('claimed') else RED),
        ('SQUAD SESSIONS', str(d.get('sessions', 0)), '3+ members on one TF21 server'),
        ('COMBAT K/D', f'{kills / deaths:.2f}' if deaths else '—', 'all linked members combined')])
    y = 1080
    spaced(draw, (PAD, y), 'BIGGEST RATING GAINS', font('mono', 24), LIME, 8)
    y += 52
    best = max((g for _, g in gains), default=1) or 1
    for i, (name, gain) in enumerate(gains, 1):
        draw.text((PAD, y), f'{i}', font=font('head', 36), fill=MUTED)
        text, f = fit(draw, short(name), 'mid', 28, 520)
        draw.text((PAD + 56, y + 4), text, font=f, fill=TEXT)
        bar(draw, (W - PAD - 360, y + 22, W - PAD - 150, y + 26), gain / best)
        right(draw, W - PAD, y, f'+{gain:,.1f}', font('head', 38), LIME)
        y += 58
    if not gains:
        draw.text((PAD, y), 'No positive gains recorded.', font=font('body', 26), fill=MUTED)
    footer(draw, height, d.get('foot') or 'Linked members · results logged this week')
    return png(img)
