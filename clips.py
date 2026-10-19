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
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import discord

log = logging.getLogger('22a.clips')
STORE_KEY = 'clips_v2'  # v2: one entry per Medal clip
REFRESH_AFTER = 6 * 3600
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


def _urls(*items):
    """Unique, non-empty URLs (Discord's proxy copy first, then the original)."""
    out = []
    for item in items:
        for url in (getattr(item, 'proxy_url', None), getattr(item, 'url', None)):
            if url and url not in out:
                out.append(url)
    return out


def _preview(message, url):
    """Title, thumbnails and video from the link preview Discord attached."""
    cid = medal_id(url)
    for embed in message.embeds:
        if not embed.url or not _medal_host(embed.url):
            continue
        if cid and medal_id(embed.url) not in (cid, None):
            continue
        video = getattr(embed, 'video', None)
        page = getattr(video, 'url', None)
        # Medal's preview usually carries the video file itself; a medal.tv page URL is a player page.
        is_page = bool(page) and (urlparse(page).hostname or '').lower() == 'medal.tv'
        return {'title': (embed.title or '')[:200] or None,
                'thumbs': _urls(embed.thumbnail, embed.image),
                'videos': [] if is_page else _urls(video),
                'player': page if is_page else None,
                'creator': getattr(getattr(embed, 'author', None), 'name', None)}
    return {'title': None, 'thumbs': [], 'videos': [], 'player': None, 'creator': None}


def _poster(message, creator):
    """Who to credit. Medal's bot posts mention the member who shared the clip."""
    author = message.author
    if not author.bot:
        return str(author.id), getattr(author, 'display_name', None) or author.name, True
    for person in getattr(message, 'mentions', []) or []:
        if not getattr(person, 'bot', False):
            return str(person.id), getattr(person, 'display_name', None) or person.name, True
    name = creator or getattr(author, 'display_name', None) or author.name
    return str(author.id), name, False


def _links(message):
    """Medal links in a message. A Medal preview card is the source of truth:
    Medal's "shared a clip" post also has a "View on Medal" link in a different
    format, which would otherwise count as a second clip."""
    cards = [e.url for e in message.embeds if e.url and _medal_host(e.url) and medal_id(e.url)]
    if cards:
        urls = cards
    else:
        parts = [message.content or '']
        for embed in message.embeds:
            parts += [embed.url or '', embed.description or '']
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
        self._refreshing = False

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
        """Add or refresh the clips in one message. Returns True if anything changed.

        One Medal clip is one entry, even when Medal posts it and then posts
        "shared a clip" as a second message."""
        if not self.ours(message.channel) or message.author.id == getattr(self.bot.user, 'id', None):
            return False
        clips, mid, changed, seen = self.state['clips'], str(message.id), False, set()
        posted = message.created_at.astimezone(timezone.utc).isoformat()
        for n, url in enumerate(_links(message)):
            cid = medal_id(url)
            key = cid or f'{mid}:{n}'
            seen.add(key)
            meta = _preview(message, url)
            author, name, member = _poster(message, meta['creator'])
            old = clips.get(key)
            clip = dict(old) if old else {'id': key, 'url': url, 'medal': cid, 'posted': posted, 'hidden': False,
                                          'messages': {}, 'thumbs': [], 'videos': []}
            clip['messages'] = {**clip.get('messages', {}), mid: {'channel': str(message.channel.id), 'votes': _votes(message)}}
            clip['posted'] = min(clip['posted'], posted)
            clip['title'] = meta['title'] or clip.get('title')
            clip['thumbs'] = meta['thumbs'] or clip.get('thumbs', [])
            clip['videos'] = meta['videos'] or clip.get('videos', [])
            clip['player'] = meta['player'] or clip.get('player')
            if member or not clip.get('member'):
                clip.update(author=author, author_name=name, member=member)
            clip['votes'] = sum(m['votes'] for m in clip['messages'].values())
            if old is None:
                # One line per new clip, so playback problems can be traced from the log.
                log.info('New clip %s: video %s; player %s', key,
                         ', '.join(f"{urlparse(v).hostname}{os.path.splitext(urlparse(v).path)[1]}" for v in clip['videos']) or 'none',
                         urlparse(clip['player']).hostname if clip.get('player') else 'none')
            same = old is not None and {k: v for k, v in clip.items() if k != 'checked'} == {k: v for k, v in old.items() if k != 'checked'}
            clip['checked'] = time.time()
            clips[key] = clip
            changed = changed or not same
        # A link edited out of the message drops this message from that clip.
        changed = self._detach(mid, keep=seen) or changed
        if changed and save:
            self.save()
        return changed

    def _detach(self, mid, keep=()):
        changed = False
        for key in [k for k, c in self.state['clips'].items() if mid in c.get('messages', {}) and k not in keep]:
            clip = self.state['clips'][key]
            del clip['messages'][mid]
            if clip['messages']:
                clip['votes'] = sum(m['votes'] for m in clip['messages'].values())
            else:
                del self.state['clips'][key]
            changed = True
        return changed

    def ours(self, channel):
        """The clips channel itself, or a post (thread) inside it if it is a forum."""
        if channel is None:
            return False
        return channel.id == self.channel or getattr(channel, 'parent_id', None) == self.channel

    def ours_id(self, channel_id):
        return channel_id == self.channel or self.ours(self.bot.get_channel(channel_id))

    def remove(self, message_id):
        if self._detach(str(message_id)):
            self.save()

    def vote(self, message_id, emoji, delta):
        if str(emoji) not in VOTES:
            return
        mid, changed = str(message_id), False
        for clip in self.state['clips'].values():
            entry = clip.get('messages', {}).get(mid)
            if entry:
                entry['votes'] = max(0, entry['votes'] + delta)
                clip['votes'] = sum(m['votes'] for m in clip['messages'].values())
                changed = True
        if changed:
            self.save()

    async def refresh_stale(self, limit=8):
        """Re-read a few older clips so expiring video/thumbnail links stay fresh."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            stale = sorted((c for c in self.state['clips'].values() if time.time() - c.get('checked', 0) > REFRESH_AFTER),
                           key=lambda c: c.get('checked', 0))[:limit]
            changed = False
            for clip in stale:
                clip['checked'] = time.time()
                for mid, info in list(clip.get('messages', {}).items()):
                    channel = self.bot.get_channel(int(info['channel']))
                    try:
                        changed = self.ingest(await channel.fetch_message(int(mid)), save=False) or changed
                        break
                    except discord.NotFound:
                        changed = self._detach(mid) or changed
                    except (discord.HTTPException, AttributeError):
                        break
            self.save()
        finally:
            self._refreshing = False

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
