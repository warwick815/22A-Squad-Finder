import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import clips

CHANNEL = 1561738686327029781


class Store:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value


def message(mid, content, embeds=(), bot=False, channel=CHANNEL, reactions=()):
    return SimpleNamespace(id=mid, content=content, embeds=list(embeds), channel=SimpleNamespace(id=channel),
                           author=SimpleNamespace(id=42, bot=bot), guild=True, reactions=list(reactions),
                           created_at=datetime(2026, 10, 19, 12, tzinfo=timezone.utc))


def preview(url, title='Bridge chaos'):
    return SimpleNamespace(url=url, title=title, thumbnail=SimpleNamespace(proxy_url='https://media.discordapp.net/x.jpg', url=None),
                           image=None, video=SimpleNamespace(url='https://medal.tv/clip/AbC123xyz'))


def service():
    return clips.Clips(SimpleNamespace(store=Store()), CHANNEL)


class ClipTests(unittest.TestCase):
    def test_medal_link_is_saved_with_preview(self):
        s = service()
        url = 'https://medal.tv/games/arma-reforger/clips/AbC123xyz/clip-title?invite=cr'
        self.assertTrue(s.ingest(message(1, f'look at this {url}', [preview(url)])))
        clip = s.state['clips']['1:0']
        self.assertEqual((clip['medal'], clip['title'], clip['player']), ('AbC123xyz', 'Bridge chaos', 'https://medal.tv/clip/AbC123xyz'))
        self.assertIn('1:0', json.loads(s.bot.store.get(clips.STORE_KEY))['clips'])

    def test_ignores_other_channels_bots_and_non_medal_links(self):
        s = service()
        self.assertFalse(s.ingest(message(1, 'https://medal.tv/clips/abcd1', channel=5)))
        self.assertFalse(s.ingest(message(2, 'https://medal.tv/clips/abcd1', bot=True)))
        self.assertFalse(s.ingest(message(3, 'https://youtube.com/watch?v=x')))
        self.assertEqual(s.state['clips'], {})

    def test_late_preview_fills_in_title(self):
        s = service()
        url = 'https://medal.tv/clips/Zz99aa'
        s.ingest(message(1, url))
        self.assertIsNone(s.state['clips']['1:0']['title'])
        s.ingest(message(1, url, [preview(url, 'Late title')]))
        self.assertEqual(s.state['clips']['1:0']['title'], 'Late title')

    def test_delete_edit_and_votes(self):
        s = service()
        s.ingest(message(1, 'https://medal.tv/clips/one111 https://medal.tv/clips/two222'))
        self.assertEqual(len(s.state['clips']), 2)
        s.ingest(message(1, 'https://medal.tv/clips/one111'))
        self.assertEqual(list(s.state['clips']), ['1:0'])
        s.vote(1, '🔥', 1); s.vote(1, '😂', 1); s.vote(1, '👍', 1); s.vote(1, '🔥', -1)
        self.assertEqual(s.state['clips']['1:0']['votes'], 1)
        s.set_hidden('1:0', True)
        self.assertTrue(s.state['clips']['1:0']['hidden'])
        s.ingest(message(1, 'https://medal.tv/clips/one111'))
        self.assertTrue(s.state['clips']['1:0']['hidden'])  # staff choice survives updates
        s.remove(1)
        self.assertEqual(s.state['clips'], {})

    def test_disabled_without_channel(self):
        import os
        old = os.environ.pop('CLIPS_CHANNEL_ID', None)
        try:
            self.assertIsNone(clips.channel_id())
        finally:
            if old is not None:
                os.environ['CLIPS_CHANNEL_ID'] = old


if __name__ == '__main__':
    unittest.main()
