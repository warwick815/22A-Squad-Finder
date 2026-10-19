"""Collects Medal clips posted in the Discord clips channel for the website.

Switched on by the CLIPS_CHANNEL_ID environment variable. It needs the
Message Content intent enabled for the bot in the Discord Developer Portal;
without the variable the bot never asks for that intent, so it cannot be
refused a connection.

Each Medal link becomes one clip. Title and thumbnail come from the preview
Discord builds for the link (which often arrives a moment after the post, via
an edit). Deleting the message removes its clips; 🔥 and 👍 reactions count
towards "top clips".
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import discord

log = logging.getLogger('22a.clips')
STORE_KEY = 'clips_v1'
MAX_CLIPS = 600
BACKFILL = 300
VOTES = {'🔥', '👍'}
MEDAL_URL = re.compile(r'https?://(?:www\.)?medal\.tv/[^\s<>()"\']+', re.I)
MEDAL_ID = re.compile(r'/clips?/([A-Za-z0-9_-]{4,40})')


def channel_id():
    raw = os.getenv('CLIPS_CHANNEL_ID', '').strip()
    return int(raw) if raw.isdecimal() else None


def medal_id(url):
    m = MEDAL_ID.search(urlparse(url).path)
    return m[1] if m else None


def _medal_host(url):
    host = (urlparse(url or '').hostname or '').lower()
    return host == 'medal.tv' or host.endswith('.medal.tv')


def _preview(message, url):
    """Title, thumbnail and player link from the link preview Discord attached."""
    cid = medal_id(url)
    for embed in message.embeds:
        if not embed.url or not _medal_host(embed.url):
            continue
        if cid and medal_id(embed.url) not in (cid, None):
            continue
        thumb = embed.thumbnail or embed.image
        video = getattr(embed, 'video', None)
        return {'title': (embed.title or '')[:200] or None,
                'thumb': getattr(thumb, 'proxy_url', None) or getattr(thumb, 'url', None),
                'player': video.url if video and _medal_host(getattr(video, 'url', None)) else None}
    return {'title': None, 'thumb': None, 'player': None}


def _links(message):
    """Medal links in the message text or in its preview cards (Medal's own
    Discord integration often posts the link only inside the card)."""
    parts = [message.content or '']
    for embed in message.embeds:
        parts += [embed.url or '', embed.description or '', embed.title or '']
        parts += [f'{f.value}' for f in getattr(embed, 'fields', [])]
    urls = [u.rstrip('.,!?*_~|') for u in MEDAL_URL.findall(' '.join(parts))]
    # One clip per Medal clip ID, so the same clip in text and card counts once.
    seen, result = set(), []
    for url in urls:
        key = medal_id(url) or url
        if key not in seen:
            seen.add(key)
            result.append(url)
    return result


def _votes(message):
    return sum(r.count for r in getattr(message, 'reactions', []) if str(r.emoji) in VOTES)


class Clips:
    def __init__(self, bot, channel):
        self.bot, self.channel = bot, channel
        try:
            self.state = json.loads(bot.store.get(STORE_KEY) or '{}')
        except ValueError:
            self.state = {}
        self.state.setdefault('clips', {})

    @classmethod
    def from_env(cls, bot):
        channel = channel_id()
        return cls(bot, channel) if channel else None

    def save(self):
        clips = self.state['clips']
        if len(clips) > MAX_CLIPS:
            for key in sorted(clips, key=lambda k: clips[k]['posted'])[:len(clips) - MAX_CLIPS]:
                del clips[key]
        self.bot.store.set(STORE_KEY, json.dumps(self.state))

    def ingest(self, message, save=True):
        """Add or refresh the clips in one message. Returns True if anything changed."""
        if not self.ours(message.channel) or message.author.id == getattr(self.bot.user, 'id', None):
            return False
        clips, changed, seen = self.state['clips'], False, set()
        for n, url in enumerate(_links(message)):
            key = f'{message.id}:{n}'
            seen.add(key)
            old = clips.get(key, {})
            meta = _preview(message, url)
            clip = {'id': key, 'message': str(message.id), 'url': url, 'medal': medal_id(url),
                    'author': str(message.author.id), 'author_name': getattr(message.author, 'display_name', None) or message.author.name,
                    'posted': message.created_at.astimezone(timezone.utc).isoformat(),
                    'title': meta['title'] or old.get('title'), 'thumb': meta['thumb'] or old.get('thumb'),
                    'player': meta['player'] or old.get('player'), 'votes': _votes(message),
                    'hidden': old.get('hidden', False)}
            if clip != old:
                clips[key] = clip
                changed = True
        # A link edited out of the message removes that clip.
        for key in [k for k in clips if k.split(':')[0] == str(message.id) and k not in seen]:
            del clips[key]
            changed = True
        if changed and save:
            self.save()
        return changed

    def ours(self, channel):
        """The clips channel itself, or a post (thread) inside it if it is a forum."""
        if channel is None:
            return False
        return channel.id == self.channel or getattr(channel, 'parent_id', None) == self.channel

    def ours_id(self, channel_id):
        return channel_id == self.channel or self.ours(self.bot.get_channel(channel_id))

    def remove(self, message_id):
        keys = [k for k in self.state['clips'] if k.split(':')[0] == str(message_id)]
        for key in keys:
            del self.state['clips'][key]
        if keys:
            self.save()

    def vote(self, message_id, emoji, delta):
        if str(emoji) not in VOTES:
            return
        changed = False
        for clip in self.state['clips'].values():
            if clip['message'] == str(message_id):
                clip['votes'] = max(0, clip.get('votes', 0) + delta)
                changed = True
        if changed:
            self.save()

    def set_hidden(self, clip_id, hidden):
        clip = self.state['clips'].get(clip_id)
        if not clip:
            raise ValueError('That clip no longer exists.')
        clip['hidden'] = bool(hidden)
        self.save()

    async def backfill(self):
        """Catch up on posts made while the bot was offline."""
        channel = self.bot.get_channel(self.channel)
        if channel is None:
            log.warning('Clips channel %s not found; check CLIPS_CHANNEL_ID', self.channel)
            return
        try:
            sources, scanned = [], 0
            if isinstance(channel, discord.ForumChannel):
                sources = list(channel.threads)
                async for thread in channel.archived_threads(limit=100):
                    sources.append(thread)
            else:
                sources = [channel]
            for source in sources:
                async for message in source.history(limit=BACKFILL):
                    scanned += 1
                    self.ingest(message, save=False)
            self.save()
            log.info('Clips ready: %d clip(s) stored after scanning %d message(s) in %s',
                     len(self.state['clips']), scanned, type(channel).__name__)
        except discord.Forbidden:
            log.warning('The bot needs View Channel and Read Message History in the clips channel')
        except discord.HTTPException:
            log.warning('Could not read clips channel history; will pick up new posts only')
        except Exception:
            log.exception('Clips catch-up failed; new posts will still be collected')

    # --- Discord event listeners -------------------------------------------
    async def on_message(self, message):
        if message.guild and self.ingest(message):
            log.info('Clip saved from message %s', message.id)

    async def on_message_edit(self, before, after):
        if after.guild:
            self.ingest(after)

    async def on_raw_message_edit(self, payload):
        # Previews often arrive as an edit to a message no longer in the cache.
        if payload.cached_message or not self.ours_id(payload.channel_id):
            return
        channel = self.bot.get_channel(payload.channel_id)
        try:
            self.ingest(await channel.fetch_message(payload.message_id))
        except (discord.HTTPException, AttributeError):
            pass

    async def on_raw_message_delete(self, payload):
        if self.ours_id(payload.channel_id):
            self.remove(payload.message_id)

    async def on_raw_reaction_add(self, payload):
        if self.ours_id(payload.channel_id):
            self.vote(payload.message_id, payload.emoji, 1)

    async def on_raw_reaction_remove(self, payload):
        if self.ours_id(payload.channel_id):
            self.vote(payload.message_id, payload.emoji, -1)

    def install(self):
        for name in ('on_message', 'on_message_edit', 'on_raw_message_edit', 'on_raw_message_delete',
                     'on_raw_reaction_add', 'on_raw_reaction_remove'):
            self.bot.add_listener(getattr(self, name), name)
