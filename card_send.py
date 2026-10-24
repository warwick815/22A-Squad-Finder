"""Turns bot data into image cards and attaches them to Discord messages.

Every message keeps a short embed (mentions, links, the footer marker used to find
earlier posts) with the card shown as its image. If a card cannot be drawn, or cards
are switched off with the Railway variable DISCORD_CARDS=false, the original text
embed is sent unchanged, so nothing is ever lost.
"""
import asyncio
import hashlib
import io
import json
import logging
import os
from datetime import datetime, timezone

import discord

log = logging.getLogger('22a.cards')
COMPARE_STATS = [('kills', 'Kills', 0, False), ('deaths', 'Deaths', 0, True), ('kd', 'K/D', 2, False),
                 ('wins', 'Wins', 0, False), ('losses', 'Losses', 0, True), ('hoursPlayed', 'Hours', 0, None),
                 ('killsPerHour', 'Kills / hour', 2, False)]


def enabled():
    return os.getenv('DISCORD_CARDS', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


async def avatar(member, size=256):
    """The member's Discord avatar as PNG bytes, or None (the card then shows the 22A crest)."""
    if member is None:
        return None
    try:
        return await asyncio.wait_for(member.display_avatar.replace(size=size, format='png').read(), timeout=6)
    except Exception:
        return None


async def draw(fn, *args):
    """Run a card function off the event loop; None if cards are off or drawing failed."""
    if not enabled():
        return None
    try:
        return await asyncio.to_thread(fn, *args)
    except Exception:
        log.exception('Could not draw %s card; sending the text version', getattr(fn, '__name__', 'a'))
        return None


def slim(embed, description=None, keep=()):
    """A short copy of an embed to sit above its card: title, colour, link, footer and
    timestamp are kept (footers mark posts the bot looks for later)."""
    out = discord.Embed(title=embed.title, url=embed.url, colour=embed.colour, timestamp=embed.timestamp,
                        description=embed.description if description is None else description)
    for field in embed.fields:
        if field.name in keep:
            out.add_field(name=field.name, value=field.value, inline=field.inline)
    if embed.footer and embed.footer.text:
        out.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
    return out


def attach(embed, png, name):
    embed.set_image(url=f'attachment://{name}')
    return discord.File(io.BytesIO(png), filename=name)


async def with_card(embed, fn, args, name, description=None, keep=()):
    """send() keyword arguments: the slim embed plus card, or the original embed alone."""
    png = await draw(fn, *args)
    if not png:
        return {'embed': embed}
    card = slim(embed, description, keep)
    return {'embed': card, 'file': attach(card, png, name)}


# --- Data for each card --------------------------------------------------------

def _number(value):
    return value if type(value) in (int, float) and value == value and value >= 0 else None


def stats_row(bot, steam):
    """Lifetime stats across WarDogs UK and TF21, the same numbers the website shows."""
    from tf21_api import combined
    panel = getattr(bot, 'player_panel', None)
    tf21 = (getattr(getattr(bot, 'tf21_api', None), 'rows', None) or {}).get(steam)
    row = combined((getattr(panel, 'rows', None) or {}).get(steam, {}), tf21)
    stats = {k: _number(row.get(k)) for k in ('kills', 'deaths', 'kd', 'wins', 'losses', 'hoursPlayed', 'killsPerHour')}
    w, l = stats['wins'], stats['losses']
    stats['winRate'] = 100 * w / (w + l) if w is not None and l is not None and w + l else None
    return stats


def position(state, steam):
    ranked = sorted((p for p in state['players'].values() if p.get('active') and not p.get('hold')),
                    key=lambda p: -p['points2'])
    me = state['players'].get(steam)
    if not me or me not in ranked:
        return None, len(ranked)
    return 1 + sum(1 for p in ranked if p['points2'] > me['points2']), len(ranked)


def profile_data(bot, member, steam, player):
    from progression import RANKS
    from rank_divisions import division, thresholds
    state = bot.progression.state
    floors = thresholds(player)
    rank = player['rank']
    combat = top = None
    try:
        from kill_feed import service, summary, weapons
        feed = service(bot).state
        combat = summary(feed, steam)
        rack = weapons(feed, steam)
        top = max(rack, key=lambda w: w['kills']) if rack else None
    except Exception:
        log.exception('Kill feed details unavailable for a profile card')
    pos, members = position(state, steam)
    status = ('Paused' if not player['active'] else 'Under review' if player.get('hold') else
              'Awaiting baseline' if player.get('baseline') is None else 'Active')
    return {'name': display(member), 'rank': rank, 'rank_name': RANKS[rank][0], 'division': division(player),
            'status': status, 'season': state.get('season', 1), 'rating': player['points2'] / 2,
            'floor': floors[rank], 'next_rank': {'name': RANKS[rank + 1][0], 'points': floors[rank + 1]} if rank < len(RANKS) - 1 else None,
            'position': pos, 'members': members, 'stats': stats_row(bot, steam), 'combat': combat, 'skill': player.get('skill'),
            'top_weapon': top and {'weapon': top['weapon'], 'kills': top['kills'], 'headshots': top.get('headshots', 0)}}


def display(member):
    return getattr(member, 'display_name', None) or getattr(member, 'name', None) or 'Member'


async def profile_message(bot, member, steam, player, embed, name='profile.png'):
    import cards
    if not enabled():
        return {'embed': embed}
    try:
        data = profile_data(bot, member, steam, player)
    except Exception:
        log.exception('Could not gather profile card data; sending the text version')
        return {'embed': embed}
    return await with_card(embed, cards.profile, (data, await avatar(member)),
                           name, keep=('Review needed', 'WARDOGS Tools — cached snapshot', '🎯 Combat rating'))


def compare_data(bot, viewer, target, viewer_member, target_member):
    from progression import RANKS
    a, b = stats_row(bot, viewer[0]), stats_row(bot, target[0])
    fmt = lambda v, d: '—' if v is None else f'{v:,.{d}f}'
    rows = [('Rank', RANKS[viewer[1]['rank']][0], RANKS[target[1]['rank']][0], viewer[1]['rank'], target[1]['rank'], False),
            ('ELO', fmt(viewer[1]['points2'] / 2, 0), fmt(target[1]['points2'] / 2, 0), viewer[1]['points2'], target[1]['points2'], False)]
    rows += [(label, fmt(a[k], d), fmt(b[k], d), a[k], b[k], lower) for k, label, d, lower in COMPARE_STATS]
    rows.append(('Win rate', fmt(a['winRate'], 1) + ('%' if a['winRate'] is not None else ''),
                 fmt(b['winRate'], 1) + ('%' if b['winRate'] is not None else ''), a['winRate'], b['winRate'], False))
    side = lambda m, p: {'name': display(m), 'rank_name': RANKS[p['rank']][0], 'rating': p['points2'] / 2}
    return {'left': side(viewer_member, viewer[1]), 'right': side(target_member, target[1]), 'rows': rows}


async def compare_message(bot, viewer, target, viewer_member, target_member, embed, name='compare.png'):
    import cards
    if not enabled():
        return {'embed': embed}
    try:
        data = compare_data(bot, viewer, target, viewer_member, target_member)
    except Exception:
        log.exception('Could not gather comparison card data; sending the text version')
        return {'embed': embed}
    pictures = (await avatar(viewer_member), await avatar(target_member))
    return await with_card(embed, cards.compare, (data, pictures), name,
                           description=(embed.description or '').split('\n')[0])


def standings_rows(bot, players):
    """Card rows for a list of saved player records, best first."""
    from progression import RANKS
    guild = bot.guild
    rows = []
    for p in sorted(players, key=lambda p: (-p['points2'], p['discord_id'])):
        member = guild.get_member(p['discord_id']) if guild else None
        note = 'Paused' if not p.get('active', True) else 'Under review' if p.get('hold') else ''
        rows.append({'name': display(member) if member else 'Former member', 'rating': p['points2'] / 2,
                     'rank': p['rank'], 'rank_name': RANKS[p['rank']][0], 'note': note, 'id': p['discord_id']})
    return rows


async def standings_message(bot, embed, data, name='standings.png'):
    import cards
    guild = bot.guild
    pictures = [await avatar(guild.get_member(r['id']) if guild else None) for r in data['rows'][:3]]
    top = data['rows'][:3]
    text = '\n'.join(f"{('🥇', '🥈', '🥉')[i]} <@{r['id']}> — **{r['rating']:,.1f}**" for i, r in enumerate(top))
    return await with_card(embed, cards.standings, (data, pictures), name, description=text or None)


async def safely(embed, build):
    """Await build() for send() arguments; on any error fall back to the text embed."""
    if not enabled():
        return {'embed': embed}
    try:
        return await build()
    except Exception:
        log.exception('Could not prepare a card; sending the text version')
        return {'embed': embed}


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]


def week_extras(bot, start, end):
    """Kill-feed highlights for the weekly card: streak of the week, sessions and the bounty."""
    try:
        from kill_feed import service, week_key
        feed = service(bot).state
    except Exception:
        return {}
    wk = week_key(start.timestamp())
    sw = feed.get('streak_week') or {}
    inside = lambda b: start.timestamp() <= (b.get('set_at') or 0) < end.timestamp()
    posted = [b for b in feed.get('bounties', []) + ([feed['bounty']] if feed.get('bounty') else [])
              if inside(b) and b.get('status') != 'cancelled']
    hunters = {}
    for b in posted:
        if b.get('claimed'):
            hunters[b.get('claimed_name')] = hunters.get(b.get('claimed_name'), 0) + 1
    top = max(hunters.items(), key=lambda kv: kv[1], default=None)
    sessions = sum(1 for s in feed.get('sessions', []) if start.timestamp() <= s['end'] < end.timestamp())
    return {'streak': sw if sw.get('week') == wk else None, 'sessions': sessions,
            'bounties': {'posted': len(posted), 'claimed': sum(1 for b in posted if b.get('claimed')),
                         'top': {'name': top[0], 'count': top[1]} if top else None}}


def now_utc():
    return datetime.now(timezone.utc)


# --- Honours card (second card when a profile is shared) --------------------

def honours_data(bot, member, steam, player):
    """Ribbon rack, morale patches and the member's best accolades."""
    from community_hq import PATCHES, PODIUM_PATCHES, locker_view
    from progression import RANKS
    from tf21_api import combined
    from website_medals import medals
    state = bot.progression.state
    panel = getattr(bot, 'player_panel', None)
    tf21 = (getattr(getattr(bot, 'tf21_api', None), 'rows', None) or {}).get(steam)
    row = combined((getattr(panel, 'rows', None) or {}).get(steam, {}), tf21)
    all_medals = medals(bot, steam, player, row)
    earned = [m for m in all_medals if m.get('earned')]
    # Season podium medals take pride of place, then the rarer awards (later in the list) first.
    ribbons = [m for m in earned if m.get('metal')] + list(reversed([m for m in earned if not m.get('metal')]))
    from patch_shop import CATALOGUE
    names = ({p['id']: p['name'] for p in PATCHES} | {pid: name for pid, name in PODIUM_PATCHES.values()}
             | {p['id']: p['name'] for p in CATALOGUE})
    box = locker_view(state, player['discord_id'])
    chosen = [p for p in box['display'] if p in box['earned']] or list(box['earned'])
    patches = [(p, names.get(p, p.title())) for p in chosen[:3] if p in names]

    accolades = []
    for m in earned:
        if m.get('metal'):
            accolades.append(('SEASON HONOURS', m['name'], m.get('detail') or 'Season podium'))
    skill = player.get('skill')
    if skill:
        accolades.append(('COMBAT RATING', f"Top {skill['top']}%", f"{skill['rating']:,} of 3,000 · x{skill['multiplier']:.2f} ELO"))
    try:
        from kill_feed import service, summary, weapons
        feed = service(bot).state
        c = summary(feed, steam) or {}
        tags = c.get('tags') or {}
        if any(tags.values()):
            accolades.append(('DOG TAGS', f"{tags.get('gold', 0)} gold", f"{tags.get('silver', 0)} silver · {tags.get('bronze', 0)} bronze collected"))
        if c.get('bounties'):
            accolades.append(('BOUNTY HUNTER', f"{c['bounties']} collected", 'Most Wanted targets taken down'))
        if (c.get('best_streak') or {}).get('count', 0) >= 5:
            accolades.append(('BEST STREAK', f"{c['best_streak']['count']} kills", f"mostly the {c['best_streak']['weapon']}"))
        rack = weapons(feed, steam)
        if rack and rack[0].get('tier'):
            accolades.append(('WEAPON MASTERY', rack[0]['weapon'], f"{rack[0]['tier']} · {rack[0]['kills']:,} kills"))
        if c.get('longest'):
            accolades.append(('LONGEST KILL', f"{c['longest']['m']:.0f}m", f"{c['longest']['weapon']}"))
    except Exception:
        log.exception('Kill feed accolades unavailable for an honours card')
    if len(accolades) < 4 and earned:
        accolades.append(('RIBBONS', f"{len(earned)} of {len(all_medals)}", 'service ribbons earned'))
    return {'name': display(member), 'rank': player['rank'], 'rank_name': RANKS[player['rank']][0],
            'season': state.get('season', 1), 'ribbons': ribbons, 'total': len(all_medals),
            'patches': patches, 'accolades': accolades[:4]}


async def honours_message(bot, member, steam, player, name='honours.png'):
    """The honours card as (embed, file), or None if cards are off or it cannot be drawn."""
    import cards
    if not enabled():
        return None
    try:
        data = honours_data(bot, member, steam, player)
    except Exception:
        log.exception('Could not gather honours card data')
        return None
    png = await draw(cards.honours, data, await avatar(member))
    if not png:
        return None
    embed = discord.Embed(title=f'🎖️ Honours · {data["name"]}', colour=0xE6C46A)
    embed.set_footer(text='22A • Ribbon rack and accolades')
    return embed, attach(embed, png, name)


async def share_message(bot, member, steam, player, embed):
    """send() arguments for a shared profile: the profile card, plus the honours card."""
    first = await profile_message(bot, member, steam, player, embed)
    second = await honours_message(bot, member, steam, player)
    if not second or 'file' not in first:
        return first
    return {'embeds': [first['embed'], second[0]], 'files': [first['file'], second[1]]}
