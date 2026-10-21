"""TF21 community server feed: all-time totals for players carrying [22A] on TF21 servers.

TF21 counts play on TF21's own servers, separate from the WarDogs UK feed, so its
counters are scored on their own baseline and added to the same ELO (see tf21_progress).
The key is read only from the environment (Railway variable tf21_api_key or TF21_API_KEY)
and is sent only to tf21.net as a Bearer token. Errors never include the key or response bodies.
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import aiohttp

log = logging.getLogger('22a.tf21')
API_URL = 'https://tf21.net/api/v1/22a-players'
SOURCE = 'tf21'
COUNTERS = ('wins', 'losses', 'kills', 'deaths')
EXTRA = ('teamKills', 'suicides')
# TF21's exact field names are not documented here, so accept the usual spellings.
ALIASES = {
    'steamId': ('steamId', 'steam_id', 'steamid', 'steam', 'steamID64', 'steam64'),
    'name': ('name', 'playerName', 'player_name', 'displayName', 'display_name', 'ign'),
    'kills': ('kills', 'totalKills', 'total_kills'),
    'deaths': ('deaths', 'totalDeaths', 'total_deaths'),
    'wins': ('wins', 'totalWins', 'total_wins'),
    'losses': ('losses', 'totalLosses', 'total_losses'),
    'teamKills': ('teamKills', 'team_kills', 'teamkills', 'tks'),
    'suicides': ('suicides', 'totalSuicides'),
    'kd': ('kd', 'kdr', 'kdRatio', 'kd_ratio'),
    'killsPerHour': ('killsPerHour', 'kills_per_hour', 'kph'),
    'online': ('online', 'isOnline', 'is_online', 'onServer', 'on_server', 'onTf21', 'on_tf21'),
}
UPDATED = ('updatedAt', 'updated_at', 'generatedAt', 'generated_at', 'timestamp', 'asOf', 'as_of')
LISTS = ('players', 'data', 'results', 'items', 'rows')


def api_key():
    return (os.getenv('tf21_api_key') or os.getenv('TF21_API_KEY') or '').strip()


def enabled():
    return bool(api_key())


def _pick(row, field):
    for key in ALIASES[field]:
        if key in row:
            return row[key]
    return None


def _count(value):
    if type(value) is int and 0 <= value <= 10**10:
        return value
    if isinstance(value, float) and value.is_integer() and 0 <= value <= 10**10:
        return int(value)
    if isinstance(value, str) and value.isdecimal() and len(value) <= 11:
        return int(value)
    return None


def normalize(payload, now=None):
    """Return (updated_iso, {steam: row}) from TF21's reply. Rows missing a valid
    Steam ID or any scoring counter are skipped rather than failing the whole feed."""
    rows = payload
    if isinstance(payload, dict):
        rows = next((payload[k] for k in LISTS if isinstance(payload.get(k), list)), None)
    if not isinstance(rows, list):
        raise ValueError('TF21 reply has no player list.')
    stamp = None
    if isinstance(payload, dict):
        raw = next((payload[k] for k in UPDATED if isinstance(payload.get(k), str)), None)
        try:
            stamp = datetime.fromisoformat(raw.replace('Z', '+00:00')) if raw else None
            if stamp and stamp.tzinfo is None:
                stamp = None
        except ValueError:
            stamp = None
    stamp = stamp or (now or datetime.now(timezone.utc))
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        steam = _pick(row, 'steamId')
        steam = str(steam) if isinstance(steam, (int, str)) else None
        if not steam or not re.fullmatch(r'\d{17}', steam) or steam in result:
            continue
        counters = {k: _count(_pick(row, k)) for k in COUNTERS}
        if any(v is None for v in counters.values()):
            continue
        entry = dict(counters)
        for k in EXTRA:
            entry[k] = _count(_pick(row, k))
        for k in ('kd', 'killsPerHour'):
            v = _pick(row, k)
            entry[k] = float(v) if isinstance(v, (int, float)) and v >= 0 else None
        online = _pick(row, 'online')
        entry['online'] = bool(online) if isinstance(online, (bool, int)) else None
        name = _pick(row, 'name')
        entry['name'] = name[:64] if isinstance(name, str) else None
        result[steam] = entry
    return stamp.isoformat(), result


class TF21API:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.rows, self.updated, self.until, self.error = {}, None, 0, None
        self.described = False

    async def fetch(self):
        async with self.lock:
            if time.monotonic() < self.until:
                if self.error:
                    raise ValueError(self.error)
                return self.updated, self.rows
            key = api_key()
            if not key:
                raise ValueError('Set tf21_api_key in Railway.')
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
                    async with session.get(API_URL, allow_redirects=False, headers={
                            'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                            'User-Agent': '22A-Discord-Bot/1.0'}) as response:
                        if response.status != 200:
                            raise ValueError(f'TF21 API HTTP {response.status}. ' + (
                                'Key rejected; check tf21_api_key.' if response.status in (401, 403)
                                else 'Retrying in five minutes.'))
                        body = bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            body.extend(chunk)
                            if len(body) > 20 * 1024 * 1024:
                                raise ValueError('TF21 API reply exceeds size limit.')
                payload = json.loads(body)
                self.updated, self.rows = normalize(payload)
                self.error = None
                if not self.described:
                    # Field names only, never values: confirms the reply layout after deploying.
                    sample = payload if isinstance(payload, list) else next((payload[k] for k in LISTS if isinstance(payload.get(k), list)), [])
                    first = sample[0] if sample and isinstance(sample[0], dict) else {}
                    log.info('TF21 feed connected: %d player row(s) usable of %d; fields %s',
                             len(self.rows), len(sample), ', '.join(sorted(first)) or 'none')
                    self.described = True
            except ValueError as exc:
                self.error = str(exc) if str(exc).startswith('TF21') or str(exc).startswith('Set') else 'TF21 API reply was not in a recognised format.'
            except (asyncio.TimeoutError, TimeoutError):
                self.error = 'TF21 API request timed out; retrying in five minutes.'
            except aiohttp.ClientError:
                self.error = 'TF21 API network error; retrying in five minutes.'
            except Exception:
                self.error = 'Unexpected TF21 API error; saved ratings retained.'
            self.until = time.monotonic() + 300
            if self.error:
                raise ValueError(self.error)
            return self.updated, self.rows


async def fetch(bot):
    if not hasattr(bot, 'tf21_api'):
        bot.tf21_api = TF21API()
    return await bot.tf21_api.fetch()


def combined(wduk_row, tf21_row):
    """Profile stats across both communities. Hours, cash and kills per hour stay
    WarDogs UK only because TF21 does not report time played."""
    row = dict(wduk_row or {})
    if not tf21_row:
        return row
    for k in COUNTERS + EXTRA:
        a, b = row.get(k), tf21_row.get(k)
        if type(b) is int:
            row[k] = (a if type(a) is int else 0) + b
    if type(row.get('kills')) is int and type(row.get('deaths')) is int:
        row['kd'] = row['kills'] / row['deaths'] if row['deaths'] else float(row['kills'])
    return row
