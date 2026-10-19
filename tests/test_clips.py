import json
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import clips

CHANNEL = 1561738686327029781
FILE = 'https://cdn.medal.tv/source/abc/clip.mp4'


class Store:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value


def person(uid, name, bot=False):
    return SimpleNamespace(id=uid, bot=bot, name=name, display_name=name)


def message(mid, content, embeds=(), author=None, channel=CHANNEL, parent=None, mentions=(), minute=0):
    return SimpleNamespace(id=mid, content=content, embeds=list(embeds), channel=SimpleNamespace(id=channel, parent_id=parent),
                           author=author or person(42, 'Poster'), guild=True, reactions=[], mentions=list(mentions),
                           created_at=datetime(2026, 10, 19, 12, minute, tzinfo=timezone.utc))


def card(url, title='Untitled - Clipped WARDOGS with Medal.tv', video=FILE, creator='WARWICK815'):
    media = lambda u: SimpleNamespace(url=u, proxy_url=None) if u else None
    return SimpleNamespace(url=url, title=title, description=None, fields=[],
                           thumbnail=SimpleNamespace(url='https://cdn.medal.tv/thumb.jpg', proxy_url='https://media.discordapp.net/external/t.jpg'),
                           image=None, video=media(video), author=SimpleNamespace(name=creator))


def service():
    bot = SimpleNamespace(store=Store(), user=SimpleNamespace(id=999), get_channel=lambda cid: None)
    return clips.Clips(bot, CHANNEL)


URL = 'https://medal.tv/games/wardogs/clips/AbC123xyz/untitled?invite=cr'
MEDAL_BOT = person(555, 'Medal', bot=True)
WARWICK = person(7, '[22A] Warwick815 [LCPL]')


class ClipTests(unittest.TestCase):
    def test_medal_two_posts_become_one_clip_credited_to_member(self):
        s = service()
        s.ingest(message(1, '', [card(URL)], author=MEDAL_BOT, minute=0))
        s.ingest(message(2, '@Warwick815 shared a clip\nView on Medal', [card(URL)], author=MEDAL_BOT, mentions=[WARWICK], minute=1))
        self.assertEqual(list(s.state['clips']), ['AbC123xyz'])
        clip = s.state['clips']['AbC123xyz']
        self.assertEqual((clip['author'], clip['author_name'], clip['member']), ('7', '[22A] Warwick815 [LCPL]', True))
        self.assertEqual(clip['videos'], [FILE])
        self.assertEqual(clip['thumbs'], ['https://media.discordapp.net/external/t.jpg', 'https://cdn.medal.tv/thumb.jpg'])
        self.assertEqual(clip['posted'], '2026-10-19T12:00:00+00:00')
        self.assertIn('AbC123xyz', json.loads(s.bot.store.get(clips.STORE_KEY))['clips'])

    def test_view_on_medal_link_in_a_different_format_is_not_a_second_clip(self):
        s = service()
        s.ingest(message(1, '', [card(URL)], author=MEDAL_BOT))
        s.ingest(message(2, '@Warwick815 shared a clip [View on Medal](https://medal.tv/clips/zZ9q8w7e6r/other)', [card(URL)],
                         author=MEDAL_BOT, mentions=[WARWICK]))
        self.assertEqual(list(s.state['clips']), ['AbC123xyz'])

    def test_embed_url(self):
        from website_clips import embed_url
        self.assertEqual(embed_url(URL), 'https://medal.tv/games/wardogs/clip/AbC123xyz/untitled?autoplay=1')
        self.assertIsNone(embed_url('https://medal.tv/'))

    def test_uncredited_medal_post_uses_medal_username(self):
        s = service()
        s.ingest(message(1, '', [card(URL)], author=MEDAL_BOT))
        clip = s.state['clips']['AbC123xyz']
        self.assertEqual((clip['author_name'], clip['member']), ('WARWICK815', False))

    def test_page_url_is_used_as_player_not_video(self):
        s = service()
        s.ingest(message(1, URL, [card(URL, video='https://medal.tv/clip/AbC123xyz')]))
        clip = s.state['clips']['AbC123xyz']
        self.assertEqual((clip['videos'], clip['player']), ([], 'https://medal.tv/clip/AbC123xyz'))

    def test_ignores_other_channels_our_bot_and_other_links(self):
        s = service()
        self.assertFalse(s.ingest(message(1, URL, channel=5)))
        self.assertFalse(s.ingest(message(2, URL, author=person(999, 'Us', bot=True))))
        self.assertFalse(s.ingest(message(3, 'https://youtube.com/watch?v=x')))
        self.assertEqual(s.state['clips'], {})

    def test_forum_threads_collected(self):
        s = service()
        self.assertTrue(s.ingest(message(9, 'https://medal.tv/clips/Forum99', channel=123, parent=CHANNEL)))

    def test_delete_one_post_keeps_clip_until_all_gone_and_votes(self):
        s = service()
        s.ingest(message(1, '', [card(URL)], author=MEDAL_BOT))
        s.ingest(message(2, '', [card(URL)], author=MEDAL_BOT, mentions=[WARWICK]))
        s.vote(1, '🔥', 1); s.vote(2, '👍', 1); s.vote(2, '😂', 1)
        self.assertEqual(s.state['clips']['AbC123xyz']['votes'], 2)
        s.set_hidden('AbC123xyz', True)
        s.remove(1)
        clip = s.state['clips']['AbC123xyz']
        self.assertEqual((clip['votes'], clip['hidden']), (1, True))
        s.remove(2)
        self.assertEqual(s.state['clips'], {})

    def test_link_edited_out_drops_clip(self):
        s = service()
        s.ingest(message(1, 'https://medal.tv/clips/one111 https://medal.tv/clips/two222'))
        self.assertEqual(sorted(s.state['clips']), ['one111', 'two222'])
        s.ingest(message(1, 'https://medal.tv/clips/one111'))
        self.assertEqual(list(s.state['clips']), ['one111'])

    def test_disabled_without_channel(self):
        old = os.environ.pop('CLIPS_CHANNEL_ID', None)
        try:
            self.assertIsNone(clips.channel_id())
        finally:
            if old is not None:
                os.environ['CLIPS_CHANNEL_ID'] = old


if __name__ == '__main__':
    unittest.main()
