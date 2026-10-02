import copy
import time
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from multidict import MultiDict

from steam_link import (COOKIE, OPENID_NS, STEAM_ENDPOINT, SteamLink, public_origin,
                        validate_assertion)

STEAM = "76561198000000001"
NOW = datetime.now(timezone.utc)


def assertion(return_to):
    claimed = "https://steamcommunity.com/openid/id/" + STEAM
    return {"openid.ns": OPENID_NS, "openid.mode": "id_res", "openid.op_endpoint": STEAM_ENDPOINT,
            "openid.return_to": return_to, "openid.claimed_id": claimed, "openid.identity": claimed,
            "openid.response_nonce": NOW.strftime("%Y-%m-%dT%H:%M:%SZ") + "unique-nonce",
            "openid.assoc_handle": "test-handle", "openid.sig": "test-signature",
            "openid.signed": "op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"}


class AssertionTests(unittest.TestCase):
    def test_valid_binding_extracts_id_but_does_not_replace_server_verification(self):
        params = assertion("https://example.test/steam/callback?state=abc")
        self.assertEqual(validate_assertion(params, params["openid.return_to"], NOW)[0], STEAM)

    def test_reject_wrong_provider_return_identity_unsigned_and_old_response(self):
        expected = "https://example.test/steam/callback?state=abc"
        edits = {"openid.op_endpoint": "https://attacker.test/", "openid.return_to": expected + "x",
                 "openid.claimed_id": "https://attacker.test/openid/id/" + STEAM,
                 "openid.identity": "https://steamcommunity.com/openid/id/76561198000000002",
                 "openid.signed": "identity,return_to", "openid.mode": "cancel",
                 "openid.response_nonce": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ") + "x"}
        for key, value in edits.items():
            with self.subTest(key=key):
                params = assertion(expected)
                params[key] = value
                with self.assertRaises(ValueError):
                    validate_assertion(params, expected, NOW)

    def test_origin_rejects_insecure_or_embedded_credentials(self):
        for value in ["http://example.test", "https://a:b@example.test", "https://example.test/path", "https://example.test?x=1"]:
            with self.assertRaises(ValueError):
                public_origin(value)
        self.assertEqual(public_origin("https://example.test/"), "https://example.test")


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MagicMock()
        self.service = SteamLink(self.bot, "https://example.test")
        self.token = self.service.issue(1)
        self.member = SimpleNamespace(id=1)
        self.bot.progression.lock = __import__("asyncio").Lock()
        self.bot.progression.find.return_value = None
        self.bot.progression.state = {"players": {}}

    def request(self, params, cookie=""):
        return SimpleNamespace(query=MultiDict(params), cookies={COOKIE: cookie})

    async def verify_session(self):
        item = self.service.get(self.token)
        item["cookie"] = "browser-secret"
        params = assertion(self.service.return_url(self.token))
        params["state"] = self.token
        self.service.check_with_steam = AsyncMock()
        response = await self.service.callback(self.request(params, "browser-secret"))
        self.assertEqual(response.status, 200)
        return params

    async def test_start_cookie_is_secure_and_redirect_is_steam(self):
        result = await self.service.begin(self.request({"state": self.token}))
        self.assertEqual(result.status, 302)
        self.assertTrue(result.headers["Location"].startswith(STEAM_ENDPOINT + "?"))
        self.assertTrue(result.cookies[COOKIE]["secure"])
        self.assertTrue(result.cookies[COOKIE]["httponly"])
        self.assertEqual(result.cookies[COOKIE]["samesite"], "Lax")

    async def test_cookie_required_before_network_verification(self):
        self.service.get(self.token)["cookie"] = "correct"
        params = assertion(self.service.return_url(self.token))
        params["state"] = self.token
        self.service.check_with_steam = AsyncMock()
        result = await self.service.callback(self.request(params, "wrong"))
        self.assertEqual(result.status, 400)
        self.service.check_with_steam.assert_not_awaited()

    async def test_verification_does_not_link_until_discord_confirmation(self):
        await self.verify_session()
        self.service.check_with_steam.assert_awaited_once()
        self.assertEqual(self.service.get(self.token)["steam_id"], STEAM)
        self.bot.progression.link.assert_not_called()
        with self.assertRaises(ValueError):
            await self.service.complete(self.token, SimpleNamespace(id=2))

    async def test_failed_steam_verification_never_sets_identity(self):
        item = self.service.get(self.token)
        item["cookie"] = "browser"
        params = assertion(self.service.return_url(self.token))
        params["state"] = self.token
        self.service.check_with_steam = AsyncMock(side_effect=ValueError("bad signature"))
        response = await self.service.callback(self.request(params, "browser"))
        self.assertEqual(response.status, 400)
        self.assertIsNone(item["steam_id"])

    async def test_replay_and_duplicate_parameters_rejected(self):
        params = await self.verify_session()
        replay = await self.service.callback(self.request(params, "browser-secret"))
        self.assertEqual(replay.status, 400)
        duplicated = MultiDict(params)
        duplicated.add("state", self.token)
        response = await self.service.callback(self.request(duplicated, "browser-secret"))
        self.assertEqual(response.status, 400)

    async def test_successful_confirmation_consumes_session(self):
        self.service.get(self.token)["steam_id"] = STEAM
        async def link(member, steam):
            self.bot.progression.state["players"][steam] = {"discord_id": member.id, "points2": 0}
        self.bot.progression.enroll_verified = AsyncMock(side_effect=link)
        self.assertEqual(await self.service.complete(self.token, self.member), STEAM)
        self.assertTrue(self.bot.progression.state["players"][STEAM]["steam_verified"])
        with self.assertRaises(ValueError):
            self.service.get(self.token)

    async def test_existing_rating_and_pause_preserved(self):
        player = {"discord_id": 1, "points2": 1234, "active": False, "hold": "review"}
        self.bot.progression.state["players"][STEAM] = player
        self.bot.progression.find.return_value = (STEAM, player)
        self.service.get(self.token)["steam_id"] = STEAM
        await self.service.complete(self.token, self.member)
        self.assertEqual(player["points2"], 1234)
        self.assertFalse(player["active"])
        self.assertEqual(player["hold"], "review")
        self.bot.progression.link.assert_not_called()

    async def test_identity_conflict_and_expired_session_rejected(self):
        self.bot.progression.state["players"][STEAM] = {"discord_id": 2}
        self.service.get(self.token)["steam_id"] = STEAM
        with self.assertRaises(ValueError):
            await self.service.complete(self.token, self.member)
        self.service.get(self.token)["expires"] = time.monotonic() - 1
        with self.assertRaises(ValueError):
            self.service.get(self.token)

    async def test_new_link_invalidates_previous_link(self):
        replacement = self.service.issue(1)
        with self.assertRaises(ValueError):
            self.service.get(self.token)
        self.assertEqual(self.service.get(replacement)["discord_id"], 1)

    async def test_check_authentication_posts_only_to_pinned_endpoint(self):
        params = assertion("https://example.test/callback")
        response = MagicMock(status=200)
        response.content.read = AsyncMock(return_value=f"ns:{OPENID_NS}\nis_valid:true\n".encode())
        response_ctx = MagicMock()
        response_ctx.__aenter__ = AsyncMock(return_value=response)
        client = MagicMock()
        client.post.return_value = response_ctx
        session_ctx = MagicMock()
        session_ctx.__aenter__ = AsyncMock(return_value=client)
        with patch("steam_link.aiohttp.ClientSession", return_value=session_ctx):
            await self.service.check_with_steam(params)
        self.assertEqual(client.post.call_args.args[0], STEAM_ENDPOINT)
        self.assertEqual(client.post.call_args.kwargs["data"]["openid.mode"], "check_authentication")
        self.assertFalse(client.post.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
