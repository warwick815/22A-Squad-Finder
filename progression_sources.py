"""Fresh Steam-ID matched progression rows with durable public-source selection."""
import logging
from leaderboard import timestamp
from wduk_api import API_SOURCE, PUBLIC_SOURCE

log = logging.getLogger('22a.sources')


async def fetch_progression(ranks):
    from wduk_api import enabled, fetch_clan
    from progression import decode_stats
    players = ranks.state['players']
    pins = ranks.state.setdefault('public_source_players', [])
    public_ids = set(pins)
    public_ids.update(s for s,p in players.items() if p.get('rating_source') == PUBLIC_SOURCE)
    if '76561197988807107' in players:
        public_ids.add('76561197988807107')
    api = None
    api_rows = {}
    api_time = None
    if enabled():
        try:
            api = await fetch_clan(ranks.bot)
            api_time, api_rows = decode_stats(api)
        except Exception:
            api = None
            log.warning('Clan feed unavailable or stale; checking public feed for linked players')
    needed = public_ids | (set(players)-set(api_rows))
    public = None
    public_rows = {}
    public_time = None
    if needed or not enabled():
        try:
            public = await ranks.fetch_public_payload()
            public_time, public_rows = decode_stats(public)
        except Exception:
            public = None
            log.warning('Public feed unavailable or stale; affected players retain their ratings')
    if api is None and public is None:
        raise ValueError('Neither progression source has valid fresh data; ratings preserved.')

    ranks.source_times = {}
    ranks.source_overrides = {}
    selected = {}
    def full_rows(payload):
        return {str(row[payload['fields'].index('steamId')]):dict(zip(payload['fields'],row)) for row in payload['players']}
    api_full = full_rows(api) if api is not None else {}
    public_full = full_rows(public) if public is not None else {}
    # Unconfigured API mode continues to expose the full public feed for admin enrolment.
    result = dict(api_rows) if enabled() else dict(public_rows)
    for steam in players:
        use_public = steam in public_ids or steam not in api_rows
        rows, full, updated, source = (public_rows, public_full, public_time, PUBLIC_SOURCE) if use_public else (api_rows, api_full, api_time, API_SOURCE)
        result.pop(steam, None)
        if steam not in rows:
            continue
        result[steam] = rows[steam]
        selected[steam] = full[steam]
        ranks.source_times[steam] = updated
        ranks.source_overrides[steam] = source
        if use_public and steam not in pins:
            pins.append(steam)
            # Pin before returning: neither API recovery nor restart switches them back.
            ranks.save()
    from season_stats import observe
    for steam,row in selected.items():
        observe(players[steam],row,ranks.source_times[steam],ranks.source_overrides[steam])
        member=ranks.bot.guild.get_member(players[steam]['discord_id']) if getattr(ranks.bot,'guild',None) else None
        if member and isinstance(member.display_name,str):players[steam]['season_name']=member.display_name
    ranks.save()
    times = list(ranks.source_times.values()) or [api_time or public_time]
    oldest = min(times, key=timestamp)
    panel = getattr(ranks.bot,'player_panel',None)
    if panel is not None:
        from wduk_api import FIELDS
        panel.record({'fields':list(FIELDS),'updatedAt':oldest,
                      'players':[[row.get(f) for f in FIELDS] for row in selected.values()]})
    from community_hq import observe as observe_operations
    observe_operations(ranks.state, selected, ranks.source_times, ranks.source_overrides)
    from fantasy import observe as observe_fantasy
    observe_fantasy(ranks.state, selected, ranks.source_times, ranks.source_overrides)
    ranks.save()
    from market_pricing import record_feed
    try:
        record_feed(ranks.bot, selected, ranks.source_times, ranks.source_overrides, players)
    except Exception:
        log.exception('Market snapshot unavailable; continuing ELO progression')
    return oldest, result
