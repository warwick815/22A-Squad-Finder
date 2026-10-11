# 22A Member HQ — Railway setup

This update adds the website to your existing bot. No domain purchase or second hosting service is required. Upload the package contents to the same repository Railway already deploys. Keep your existing variables and persistent Volume. Do not replace, delete or move `/data/22a.sqlite3`.

## 1. Add Discord sign-in (one-time setup)

1. Open https://discord.com/developers/applications and choose the application for your existing 22A bot.
2. Open **OAuth2**. Add a redirect URL consisting of your existing Railway public address followed by `/auth/callback`. For example, if your `STEAM_LINK_BASE_URL` is `https://example.up.railway.app`, add `https://example.up.railway.app/auth/callback`.
3. In Railway, open your bot service → **Variables**. Add:
   - `WEBSITE_DISCORD_CLIENT_ID`: the application's Client ID.
   - `WEBSITE_DISCORD_CLIENT_SECRET`: its OAuth2 Client Secret. This is different from your bot token. Paste it only into Railway, never Discord or GitHub.
4. Leave `STEAM_LINK_BASE_URL` as your existing HTTPS address, with no path. Leave `PORT` managed by Railway. Keep one replica of the bot.
5. Deploy the update, then open your Railway address in a browser. Share that address in Discord.

The homepage works without the two new variables, but shows that sign-in needs setup. Sign-in requests only Discord's `identify` scope. The bot checks server membership before serving member data or changing specialities.

## Included in this first version

- 22A green/purple design using the supplied skull logo, responsive for phones.
- Discord sign-in, using existing Steam links and saved ratings.
- Current-season standings, searchable by member name, refreshed from the bot every minute (the underlying game feed normally updates every five minutes).
- Player profiles with rank artwork, progress, lifetime combat stats, own rating history and cached WARDOGS Tools stats.
- Other-player profiles and side-by-side comparisons, with text and colour for differences.
- Speciality selection: one primary and up to three secondaries, saving through the existing Discord role synchroniser. The roster reflects actual Discord roles.
- Clear source timestamps and stale-data notices. The website cannot make WARDOGS Tools sync sooner.

Continue to use Discord for Steam linking, connecting Tools profiles, preferred teams/general play classes, betting, staff tools, season resets and announcements. This release does not add website administration or betting controls.

## Data and sessions

The website reads the same in-memory services and SQLite database as the bot. It creates no second player database, awards no points itself and does not reset player data. Role changes are restricted to the signed-in member's cosmetic specialities. Existing role safety checks still apply.

Website sign-in lasts up to 12 hours. A bot deployment ends website sessions, so members may need to sign into the website again. Their Steam link, ELO, history and preferences remain saved; Steam relinking is not required.

Private API responses are not cached. OAuth state is browser-bound and single-use; session cookies are Secure/HttpOnly and writes require a same-origin CSRF token. Tokens and client secrets never enter frontend files. HTTPS is required. The existing Steam callback and `/health` routes remain available.

Run `/roles-panel` in Discord if speciality roles have not yet been created. If a role update fails, the saved choice is marked pending and the existing bot loop retries; check Manage Roles and the bot's role hierarchy.

## Preview and verification

Add `?demo=1` to the homepage URL to inspect the design with clearly labelled fictional players. Demo mode never changes Discord roles. Remove that query for the real site. The preview is not proof that production sign-in works.

Before announcing the website, sign in as a server member, open a profile and comparison, save a speciality and verify it in Discord. Check that a non-member is denied. Live verification requires your Railway deployment and OAuth credentials; it cannot be completed from the package alone.

Visual structure inspired by https://ironcrest.gg/; original 22A styling, copy and supplied logo. Discord OAuth implementation follows https://discord.com/developers/docs/topics/oauth2.
