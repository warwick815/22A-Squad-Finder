"""Steam OpenID linking with a final confirmation by the initiating Discord user."""
import asyncio
import html
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

import aiohttp
from aiohttp import web
import discord
from discord import app_commands

log = logging.getLogger("22a.steam_link")
STEAM_ENDPOINT = "https://steamcommunity.com/openid/login"
OPENID_NS = "http://specs.openid.net/auth/2.0"
COOKIE = "__Host-22a-link"
TTL = 600


def public_origin(value):
    parsed = urlsplit(value.strip())
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("STEAM_LINK_BASE_URL must be your public HTTPS origin, without a path or query.")
    return f"https://{parsed.netloc}"


def validate_assertion(params, expected_return, now=None):
    """Validate local bindings first; caller must also verify the signature directly with Steam."""
    if params.get("openid.ns") != OPENID_NS or params.get("openid.mode") != "id_res":
        raise ValueError("Steam sign-in was cancelled or returned an invalid response.")
    if params.get("openid.op_endpoint") != STEAM_ENDPOINT:
        raise ValueError("Unexpected Steam provider endpoint.")
    if params.get("openid.return_to") != expected_return:
        raise ValueError("Steam response does not belong to this sign-in request.")
    claimed = params.get("openid.claimed_id", "")
    match = re.fullmatch(r"https?://steamcommunity\.com/openid/id/(\d{17})", claimed)
    if not match or params.get("openid.identity") != claimed:
        raise ValueError("Steam identity is invalid.")
    required = {"op_endpoint", "claimed_id", "identity", "return_to", "response_nonce", "assoc_handle"}
    signed = set(params.get("openid.signed", "").split(","))
    if not required.issubset(signed) or not params.get("openid.sig") or not params.get("openid.assoc_handle"):
        raise ValueError("Steam response is missing required signed fields.")
    nonce = params.get("openid.response_nonce", "")
    try:
        issued = datetime.strptime(nonce[:20], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Invalid Steam response timestamp.") from None
    age = ((now or datetime.now(timezone.utc)) - issued).total_seconds()
    if not nonce[20:] or age > TTL or age < -60:
        raise ValueError("Steam response has expired. Run /link again.")
    return match.group(1), nonce


def page(title, text, status=200):
    body = ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>22A — {html.escape(title)}</title><body><main><h1>{html.escape(title)}</h1>"
            f"<p>{html.escape(text)}</p><p>22A WarDogs Community</p></main></body></html>")
    return web.Response(text=body, status=status, content_type="text/html", headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})


class SteamLink:
    def __init__(self, bot, origin, port=8080):
        self.bot, self.origin, self.port = bot, public_origin(origin), port
        self.sessions = {}
        self.nonces = {}
        self.lock = asyncio.Lock()
        self.runner = None

    @classmethod
    def from_env(cls, bot):
        origin = os.getenv("STEAM_LINK_BASE_URL", "").strip()
        if not origin:
            return None
        if bot.progression is None:
            raise ValueError("Enable rank progression with RANK_ANNOUNCEMENT_CHANNEL_ID before Steam linking.")
        port = int(os.getenv("PORT", "8080"))
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535.")
        return cls(bot, origin, port)

    def purge(self):
        now = time.monotonic()
        self.sessions = {k: v for k, v in self.sessions.items() if v["expires"] > now}
        self.nonces = {k: v for k, v in self.nonces.items() if v > now}

    def issue(self, discord_id):
        self.purge()
        if len(self.sessions) >= 500:
            raise ValueError("Too many pending links. Try again in a few minutes.")
        self.sessions = {k: v for k, v in self.sessions.items() if v["discord_id"] != discord_id}
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {"discord_id": discord_id, "expires": time.monotonic() + TTL,
                                "cookie": None, "steam_id": None}
        return token

    def get(self, token, discord_id=None):
        self.purge()
        item = self.sessions.get(token)
        if item is None:
            raise ValueError("This link expired or the bot restarted. Run /link again.")
        if discord_id is not None and item["discord_id"] != discord_id:
            raise ValueError("Only the member who ran /link can confirm this account.")
        return item

    def return_url(self, token):
        return f"{self.origin}/steam/callback?{urlencode({'state': token})}"

    async def health(self, request):
        return web.Response(text="22A Steam linking service", headers={"Cache-Control": "no-store"})

    async def begin(self, request):
        try:
            if len(request.query.getall("state", [])) != 1:
                raise ValueError("Invalid link request. Run /link in Discord.")
            token = request.query["state"]
            async with self.lock:
                item = self.get(token)
                if item["steam_id"]:
                    return page("Steam account verified", "Return to Discord and select Review Steam account.")
                item["cookie"] = secrets.token_urlsafe(32)
                params = {"openid.ns": OPENID_NS, "openid.mode": "checkid_setup",
                          "openid.return_to": self.return_url(token), "openid.realm": self.origin + "/",
                          "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
                          "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select"}
                response = web.HTTPFound(STEAM_ENDPOINT + "?" + urlencode(params))
                response.headers["Cache-Control"] = "no-store"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.set_cookie(COOKIE, item["cookie"], secure=True, httponly=True, samesite="Lax", path="/", max_age=TTL)
                return response
        except ValueError as error:
            return page("Cannot start sign-in", str(error), 400)

    async def check_with_steam(self, params):
        body = {k: v for k, v in params.items() if k.startswith("openid.")}
        body["openid.mode"] = "check_authentication"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(STEAM_ENDPOINT, data=body, allow_redirects=False) as response:
                if response.status != 200:
                    raise ValueError("Steam verification is unavailable. Try /link again shortly.")
                raw = await response.content.read(16385)
                if len(raw) > 16384:
                    raise ValueError("Unexpected Steam verification response.")
                values = {}
                for line in raw.decode("utf-8").splitlines():
                    key, separator, value = line.partition(":")
                    if separator:
                        if key in values:
                            raise ValueError("Invalid Steam verification response.")
                        values[key] = value.strip()
                if values.get("is_valid") != "true" or values.get("ns") != OPENID_NS:
                    raise ValueError("Steam could not verify this sign-in. Run /link again.")

    async def callback(self, request):
        try:
            if any(len(request.query.getall(key)) != 1 for key in request.query):
                raise ValueError("Duplicate sign-in parameters are not allowed.")
            token = request.query.get("state", "")
            async with self.lock:
                item = self.get(token)
                if not item["cookie"] or not secrets.compare_digest(request.cookies.get(COOKIE, ""), item["cookie"]):
                    raise ValueError("Open the sign-in link and finish Steam login in the same browser. Then run /link again if needed.")
                if item["steam_id"]:
                    raise ValueError("This sign-in response has already been used. Return to Discord to confirm.")
                steam, nonce = validate_assertion(dict(request.query), self.return_url(token))
                if nonce in self.nonces:
                    raise ValueError("This Steam response has already been used.")
                await self.check_with_steam(dict(request.query))
                self.get(token)  # Recheck expiration after the network request.
                item["steam_id"] = steam
                self.nonces[nonce] = time.monotonic() + TTL
            result = page("Steam account verified", "Return to your private /link message in Discord. "
                          "Select Review Steam account, check the profile, then Confirm link. Nothing is linked until you confirm there.")
            result.del_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
            return result
        except ValueError as error:
            return page("Could not verify Steam", str(error), 400)
        except Exception:
            # Do not log the callback URL, cookie, assertion or session token.
            log.warning("Steam callback failed; user can retry /link")
            return page("Steam unavailable", "Could not complete verification. Please run /link again shortly.", 503)

    async def complete(self, token, member):
        async with self.lock:
            item = self.get(token, member.id)
            steam = item["steam_id"]
            if not steam:
                raise ValueError("Finish signing in on Steam first.")
            ranks = self.bot.progression
            async with ranks.lock:
                existing = ranks.find(member.id)
                registered = ranks.state["players"].get(steam)
                if (existing and existing[0] != steam) or (registered and registered["discord_id"] != member.id):
                    raise ValueError("That Discord or Steam account already has a different link. Ask an admin; ranks cannot be reset by relinking.")
                if not registered:
                    await ranks.link(member, steam)
                player = ranks.state["players"][steam]
                player["steam_verified"] = True
                ranks.save()
                del self.sessions[token]
                return steam

    async def start(self):
        app = web.Application(client_max_size=32768)
        app.router.add_get("/health", self.health)
        app.router.add_get("/steam/start", self.begin)
        app.router.add_get("/steam/callback", self.callback)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        await web.TCPSite(self.runner, host="0.0.0.0", port=self.port).start()
        log.info("Steam link callback listening on configured PORT")

    async def close(self):
        if self.runner:
            await self.runner.cleanup()


class LinkView(discord.ui.View):
    def __init__(self, service, token, confirm=False):
        super().__init__(timeout=TTL)
        self.service, self.token = service, token
        self.confirm = confirm
        if not confirm:
            self.add_item(discord.ui.Button(label="Sign in through Steam", style=discord.ButtonStyle.link,
                          url=f"{service.origin}/steam/start?{urlencode({'state': token})}"))
        button = discord.ui.Button(label="Confirm link" if confirm else "Review Steam account", style=discord.ButtonStyle.success)
        button.callback = self.clicked
        self.add_item(button)

    async def clicked(self, interaction):
        self.service.bot.validate_context(interaction)
        item = self.service.get(self.token, interaction.user.id)
        if not item["steam_id"]:
            raise ValueError("Complete Steam sign-in first, then return here and press Review Steam account.")
        if not self.confirm:
            steam = item["steam_id"]
            await interaction.response.send_message(
                f"Steam verified this account: https://steamcommunity.com/profiles/{steam}\n"
                "Confirm only if this is your account. New players start at Private / 0; existing ratings are kept.",
                view=LinkView(self.service, self.token, confirm=True), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        steam = await self.service.complete(self.token, interaction.user)
        await interaction.followup.send(f"Steam linked: https://steamcommunity.com/profiles/{steam}\n"
                                        "Use /rank to see your progression. Existing ratings and pause/hold status are preserved.", ephemeral=True)
        self.stop()

    async def on_error(self, interaction, error, item):
        message = str(error) if isinstance(error, ValueError) else "Could not finish linking. Try again or ask an admin to check permissions. Any saved rating is preserved."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


@app_commands.command(name="link", description="Verify and link your Steam account automatically for 22A progression")
@app_commands.guild_only()
async def link_command(interaction: discord.Interaction):
    bot = interaction.client
    bot.validate_context(interaction)
    service = bot.steam_link
    if not service:
        raise ValueError("Steam sign-in is not configured yet. Ask an admin to set STEAM_LINK_BASE_URL.")
    bot.progression.roles()
    bot.progression.channel()
    async with service.lock:
        token = service.issue(interaction.user.id)
    await interaction.response.send_message("Sign in on Steam's website, then return here to review and confirm your account. "
        "This private link expires in 10 minutes. Do not share it. Your Steam password is never entered into the bot.",
        view=LinkView(service, token), ephemeral=True)
