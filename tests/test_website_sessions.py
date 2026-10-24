"""Website sign-ins survive restarts, last 30 days, renew with use and allow several devices."""
import asyncio
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from aiohttp.test_utils import make_mocked_request

import website
from website import SESSION_COOKIE, SESSION_STORE, STATE_COOKIE, Website


class Store(dict):
    def get(self, key, default=None): return super().get(key, default)
    def set(self, key, value): self[key] = value


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        member = NS(id=123)
        self.bot = NS(initialized=True, store=self.store, guild=NS(fetch_member=AsyncMock(return_value=member)))
        self.site = self.make_site()

    def make_site(self):
        site = Website(self.bot, 'https://example.test')
        site.client_id, site.client_secret = '1', 'secret'
        site.exchange = AsyncMock(return_value=123)
        return site

    def sign_in(self, site=None):
        site = site or self.site
        login = asyncio.run(site.login(make_mocked_request('GET', '/auth/login')))
        query = parse_qs(urlsplit(login.location).query)
        self.assertEqual(query['prompt'], ['none'])  # Returning members skip Discord's approval screen.
        request = make_mocked_request('GET', f"/auth/callback?state={query['state'][0]}&code=x",
                                      headers={'Cookie': f'{STATE_COOKIE}={login.cookies[STATE_COOKIE].value}'})
        response = asyncio.run(site.callback(request))
        cookie = response.cookies[SESSION_COOKIE]
        self.assertEqual(int(cookie['max-age']), 30 * 86400)
        return cookie.value

    def request(self, sid):
        return make_mocked_request('GET', '/api/dashboard', headers={'Cookie': f'{SESSION_COOKIE}={sid}'})

    def test_sign_in_survives_a_restart_and_only_a_hash_is_stored(self):
        sid = self.sign_in()
        self.assertNotIn(sid, self.store[SESSION_STORE])
        restarted = self.make_site()
        self.assertEqual(restarted.session(self.request(sid))['uid'], 123)

    def test_several_devices_stay_signed_in_up_to_five(self):
        sids = [self.sign_in() for _ in range(6)]
        restarted = self.make_site()
        for sid in sids[1:]:
            self.assertEqual(restarted.session(self.request(sid))['uid'], 123)
        with self.assertRaises(website.web.HTTPUnauthorized):
            restarted.session(self.request(sids[0]))  # The oldest of six is dropped.

    def test_use_renews_and_expiry_still_applies(self):
        sid = self.sign_in()
        key = Website.sid_hash(sid)
        self.site.saved[key]['expires_at'] = time.time() + 5 * 86400  # Not used for a while.
        request = self.request(sid)
        self.site.session(request)
        self.assertEqual(request.get('renew_session'), sid)
        self.assertGreater(self.site.saved[key]['expires_at'], time.time() + 29 * 86400)
        self.site.saved[key]['expires_at'] = time.time() - 1
        self.site.sessions.clear()
        with self.assertRaises(website.web.HTTPUnauthorized):
            self.site.session(self.request(sid))

    def test_logout_ends_the_saved_sign_in(self):
        sid = self.sign_in()
        request = make_mocked_request('POST', '/auth/logout', headers={'Cookie': f'{SESSION_COOKIE}={sid}', 'Origin': 'https://example.test',
                                                                       'X-CSRF-Token': self.site.sessions[sid]['csrf']})
        asyncio.run(self.site.logout(request))
        with self.assertRaises(website.web.HTTPUnauthorized):
            self.make_site().session(self.request(sid))


if __name__ == '__main__':
    unittest.main()
