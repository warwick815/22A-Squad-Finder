"""Discord cards for the kill feed: new bounties, claimed bounties and squad after-action reports."""
import logging
from datetime import datetime, timezone

import discord

log = logging.getLogger('22a.field_reports')
LIME, RED, GOLD = 0xA6E35A, 0xE0525C, 0xE6C46A


def _who(bot, steam, fallback):
    """A member mention when the Steam ID is linked (shown without pinging), else the in-game name."""
    players = getattr(getattr(bot, 'progression', None), 'state', {}).get('players', {})
    p = players.get(str(steam))
    return f"<@{p['discord_id']}>" if p else discord.utils.escape_markdown(str(fallback))


def _when(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def _times(n):
    return 'time' if n == 1 else 'times'


def _until(e):
    """When an hourly bounty runs out, in UK time (e.g. '21:00')."""
    from kill_feed import UK
    expires = e.get('expires') or ((e.get('hour') or 0) + 1) * 3600
    return datetime.fromtimestamp(expires, UK).strftime('%H:%M')


def embed_for(bot, e):
    if e['type'] == 'bounty_set':
        embed = discord.Embed(title=f"🎯 Most Wanted: {e['name']}", colour=RED,
            description=(f"Killed 22A members **{e['kills']}** {_times(e['kills'])} in the last hour.\n"
                         f"First member to take them down on a TF21 server before {_until(e)} claims the bounty, "
                         "the **Bounty hunter** ribbon and bragging rights."))
        embed.set_footer(text=f'22A field reports · Bounty runs until {_until(e)} UK time')
        return embed
    if e['type'] == 'bounty_claimed':
        how = e.get('weapon') or 'unknown weapon'
        if e.get('distance') is not None:
            how += f" at {e['distance']:.0f} m"
        if e.get('headshot'):
            how += ', headshot'
        embed = discord.Embed(title='💀 Bounty claimed', colour=GOLD,
            description=f"{_who(bot, e['claimed'], e.get('claimed_name'))} took down **{discord.utils.escape_markdown(e['name'])}** ({how}).")
        embed.set_footer(text='22A field reports · Bounty hunter ribbon awarded')
        return embed
    # Squad session after-action report.
    minutes = max(1, round((e['end'] - e['start']) / 60))
    squad = '\n'.join(f"{_who(bot, m['steam'], m['name'])} · **{m['kills']}** kills"
                      + (f" ({m['headshots']} HS)" if m['headshots'] else '') for m in e['members'][:10])
    embed = discord.Embed(title=f"🪖 After-action report · {str(e['server']).upper()}{' · ' + e['map'] if e.get('map') else ''}",
                          colour=LIME, timestamp=_when(e['end']),
                          description=f"**{len(e['members'])}** members, **{e['kills']}** kills in {minutes} min.")
    embed.add_field(name='Squad', value=squad or '—', inline=False)
    embed.add_field(name='Top gun', value=f"{_who(bot, e['top']['steam'], e['top']['name'])} · {e['top']['kills']} kills", inline=True)
    if e.get('longest'):
        embed.add_field(name='Longest shot', value=f"{discord.utils.escape_markdown(e['longest']['name'])} · {e['longest']['m']:.0f} m ({e['longest']['weapon']})", inline=True)
    if e.get('weapon'):
        embed.add_field(name='Weapon of choice', value=f"{e['weapon'][0]} · {e['weapon'][1]} kills", inline=True)
    embed.set_footer(text='22A field reports · TF21 servers')
    return embed


def _member(bot, steam):
    players = getattr(getattr(bot, 'progression', None), 'state', {}).get('players', {})
    p, guild = players.get(str(steam)), getattr(bot, 'guild', None)
    return guild.get_member(p['discord_id']) if p and guild else None


async def message_for(bot, e):
    """Keyword arguments for channel.send: the image card with a short embed, or the
    text embed alone if the card cannot be drawn (so a report is never lost)."""
    import aar_card
    import cards
    from card_send import avatar, with_card
    embed = embed_for(bot, e)
    if e['type'] in ('bounty_set', 'bounty_claimed'):
        import playing_card
        deck_id, n = e['deck'], e['card']
        claimed = e['type'] == 'bounty_claimed'
        card = {**e, 'n': n, 'status': 'claimed' if claimed else 'open'}
        name = playing_card.label(n)
        if claimed:
            deck = (getattr(getattr(bot, 'kill_feed', None), 'state', None) or {}).get('deck', {}).get(deck_id, {})
            text = (f"{_who(bot, e['claimed'], e.get('claimed_name'))} collected the **{name}**: "
                    f"**{discord.utils.escape_markdown(e['name'])}** is down. "
                    f"{len(deck)} of 53 cards collected in {playing_card.deck_label(deck_id)}.")
        else:
            crime = (f"Called in by staff: last killed {discord.utils.escape_markdown(e.get('last_victim') or 'a 22A member')}." if e.get('manual')
                     else f"Killed 22A members **{e['kills']}** {_times(e['kills'])} in the last hour.")
            text = (f"Up for grabs: the **{name}**. {crime} "
                    f"First to take them down on a TF21 server before {_until(e)} collects the card.")
        return await with_card(embed, playing_card.render, (card, deck_id), 'most-wanted-card.png', description=text)
    squad = ' '.join(_who(bot, m['steam'], m['name']) for m in e['members'][:10])
    return await with_card(embed, aar_card.render, (e, await avatar(_member(bot, e['top']['steam']))), 'after-action.png',
                           description=f'**Squad:** {squad}')
