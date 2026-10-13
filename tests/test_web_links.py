import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from web_links import web_button, web_view, components_changed
from betting import BettingPanel
from player_panel import PlayerView

class WebLinksTests(unittest.IsolatedAsyncioTestCase):
    async def test_links_use_configured_origin_and_destination(self):
        with patch.dict(os.environ,{'STEAM_LINK_BASE_URL':'https://22a.up.railway.app/'}):
            view=web_view('standings')
            self.assertEqual(view.children[0].label,'Web View')
            self.assertEqual(view.children[0].url,'https://22a.up.railway.app/#standings')
            for view,section in [(BettingPanel(),'club'),(PlayerView(NS()),'profile')]:
                buttons=[b for b in view.children if getattr(b,'label',None)=='Web View']
                self.assertEqual(len(buttons),1)
                self.assertEqual(buttons[0].url,'https://22a.up.railway.app/#'+section)
                view.to_components()
    async def test_invalid_origin_omits_link(self):
        for origin in ('','http://bad.test','https://good.test/auth/callback','https://user:secret@good.test','https://good.test?query=1'):
            with patch.dict(os.environ,{'STEAM_LINK_BASE_URL':origin}):self.assertIsNone(web_button('club'))
    async def test_existing_message_component_changes_detected(self):
        with patch.dict(os.environ,{'STEAM_LINK_BASE_URL':'https://22a.up.railway.app'}):
            view=web_view('standings')
            self.assertTrue(components_changed(NS(components=[]),view))
            components=[NS(to_dict=lambda c=c:c) for c in view.to_components()]
            self.assertFalse(components_changed(NS(components=components),view))
