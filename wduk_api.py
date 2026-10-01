"""Authenticated 22A clan API. Credentials are read only from the environment."""
import asyncio
import json
import os
import time
import aiohttp

API_URL = 'https://hq.wardogs.uk/api/clans/22A/players'
API_SOURCE = 'wduk-clan-22A-all-v1'
PUBLIC_SOURCE = 'wardogs-public-all-v1'
FIELDS = ('steamId','name','kills','deaths','kd','hoursPlayed','cashEarned','lastSeenMinsAgo','online','favouriteServer','killsPerHour','teamKills','suicides','wins','losses')


def enabled():
    return bool(os.getenv('WDUK_API_KEY','').strip())


def source_id():
    return API_SOURCE if enabled() else PUBLIC_SOURCE


def normalize(payload):
    if not isinstance(payload,dict) or payload.get('tag') != '22A' or payload.get('period') != 'all':
        raise ValueError('Unexpected WDUK clan or period; ratings unchanged.')
    if not isinstance(payload.get('players'),list):
        raise ValueError('Invalid WDUK players response.')
    rows=[]
    for row in payload['players']:
        if not isinstance(row,dict) or not set(FIELDS).issubset(row):
            raise ValueError('WDUK player fields changed; ratings unchanged.')
        rows.append([row[k] for k in FIELDS])
    result={'updatedAt':payload.get('updatedAt'),'fields':list(FIELDS),'players':rows}
    from leaderboard import decode_feed
    from progression import decode_stats
    decode_feed(result)
    decode_stats(result)  # Includes timestamp freshness, duplicate IDs and counter checks.
    return result


class ClanAPI:
    def __init__(self):
        self.lock=asyncio.Lock()
        self.payload=None
        self.until=0
        self.error=None

    async def fetch(self):
        async with self.lock:
            if time.monotonic()<self.until:
                if self.error:
                    raise ValueError(self.error)
                # Revalidate age even when serving a cached response.
                from progression import decode_stats
                decode_stats(self.payload)
                return self.payload
            key=os.getenv('WDUK_API_KEY','').strip()
            if not key:
                raise ValueError('Set WDUK_API_KEY in Railway.')
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
                    async with session.get(API_URL,headers={'X-Api-Key':key,'Accept':'application/json','User-Agent':'22A-Discord-Bot/1.0'},allow_redirects=False) as response:
                        if response.status != 200:
                            raise ValueError(f'WDUK API returned HTTP {response.status}; saved ratings retained.')
                        body=bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            body.extend(chunk)
                            if len(body)>20*1024*1024:
                                raise ValueError('WDUK API response exceeds size limit.')
                        self.payload=normalize(json.loads(body))
                self.error=None
            except Exception:
                # Never include response bodies, request headers or credentials in logs.
                self.error='WDUK API unavailable or invalid. Check key, service status and source timestamp; ratings retained.'
                self.until=time.monotonic()+300
                raise ValueError(self.error) from None
            self.until=time.monotonic()+300
            return self.payload


async def fetch_clan(bot):
    if not hasattr(bot,'clan_api'):
        bot.clan_api=ClanAPI()
    return await bot.clan_api.fetch()


def apply_source(player,counters,updated,source):
    """Each player migrates once; absent players wait for their own first valid row."""
    previous=player.get('rating_source',PUBLIC_SOURCE)
    if previous == source:
        return False
    if player.get('pending'):
        return True  # Deliver pending Discord events before moving the baseline.
    player.update(baseline=counters.copy(),updated=updated,rating_source=source)
    return True
