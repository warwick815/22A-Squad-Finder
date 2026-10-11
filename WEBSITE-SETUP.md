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

## Included in Member HQ v2

- Green/purple 22A design with a centred crest, grid background, bold headings and mobile layouts, inspired by wardogs.uk.
- Personal dashboard: season position, recent points, next promotion and separate combat/Tools source status.
- Own rating chart with 7-day, 30-day and season views, plus recorded scoring breakdowns. Old events without detailed breakdowns remain visible without invented figures.
- Searchable standings sorted by ELO, K/D, kills, win rate or kills/hour; season Hall of Fame.
- Weekly position movement uses actual saved standings. It appears after at least seven days of history; snapshots are recorded when members open the website.
- Profiles with avatars, rank artwork and display-only milestones. Share your own profile to #wardogs-chat after reviewing the confirmation; the existing five-minute share cooldown applies.
- Speciality selection and roster; visible active squads with join/leave controls and a voice link after joining. Private squads are shown only to their existing members. Missing-role suggestions are advisory.
- Staff dashboard for members with Manage Server: review player status and Steam links, pause/resume scoring, adjust ratings, approve verified Tools profiles and close a season. Every write requires review/confirmation and is recorded in a website staff log.

Staff resume requires a fresh player snapshot and preserves the saved rating. Tools approval requires staff to independently check ownership and starts a new level baseline; it does not award historical levels. Season close archives standings and resets seasonal ratings, preserving links and history. Discord role/announcement changes are handled by the bot's normal update loop.

Continue to use Discord for Steam linking, preferred teams/general play classes, betting, creating squads and announcements. The website does not change Steam identity links. Cached Tools data remains subject to the provider's own sync schedule.

## Updating an existing website

Replace the repository files with this package's contents and let Railway redeploy. Keep all current variables and the persistent volume. No additional environment variables or database reset are needed for v2. A deployment signs website users out; they can sign in again.

For your current Railway address, these two settings are deliberately different:

- Railway `STEAM_LINK_BASE_URL`: `https://22a.up.railway.app`
- Discord OAuth2 redirect: `https://22a.up.railway.app/auth/callback`

Do not put `/auth/callback` in `STEAM_LINK_BASE_URL`.

## Data and sessions

The website reads the same in-memory services and SQLite database as the bot. It creates no second player database, does not reset data during deployment. Explicit staff adjustments and season-end actions can change ratings. Role changes are restricted to the signed-in member's cosmetic specialities. Existing role safety checks still apply.

Website sign-in lasts up to 12 hours. A bot deployment ends website sessions, so members may need to sign into the website again. Their Steam link, ELO, history and preferences remain saved; Steam relinking is not required.

Private API responses are not cached. OAuth state is browser-bound and single-use; session cookies are Secure/HttpOnly and writes require a same-origin CSRF token. Tokens and client secrets never enter frontend files. HTTPS is required. The existing Steam callback and `/health` routes remain available.

Run `/roles-panel` in Discord if speciality roles have not yet been created. If a role update fails, the saved choice is marked pending and the existing bot loop retries; check Manage Roles and the bot's role hierarchy.

## Preview and verification

Add `?demo=1` to the homepage URL to inspect the design with clearly labelled fictional players. Demo mode never changes Discord, ratings or seasons. Remove that query for the real site. The preview is not proof that production sign-in works.

Before announcing the website, sign in as a server member, open a profile and comparison, save a speciality and verify it in Discord. Check that a non-member is denied. Live verification requires your Railway deployment and OAuth credentials; it cannot be completed from the package alone.

Visual structure inspired by https://wardogs.uk/ and the earlier https://ironcrest.gg/ reference; original 22A styling, copy and supplied logo. Discord OAuth implementation follows https://discord.com/developers/docs/topics/oauth2.


## Member HQ v3 — Challenge Club, medals and graphs

Upload the full package contents to your existing bot repository. No new variables, domain changes or database reset are required. Keep the persistent Railway volume. The live website address is https://22a.up.railway.app.

### Challenge Club

Members can create, accept, decline or cancel unaccepted offers from the website, with a terms review before any change. The website uses the bot's existing betting wallet, lock and settlement engine. It supports kills targets, most-kills races, and kills targets with death limits. Starting balances remain $10,000 once; stakes remain $100–$1,000 each. No real money, purchases, cash-out, prizes or ELO changes.

Staff must already have posted `/betting-panel`. Players must be Steam-linked server members with access to that channel. Offers are published through the existing bot loop; existing Discord offers appear on the website too. The page shows available/reserved balances, up to 50 personal challenges, saved progress and results. Press Refresh challenges for the latest data. An active challenge cannot be cancelled by a player. Existing snapshot tolerances and refund rules apply; the website cannot force fresher game data.

### Medals

Twelve display-only achievements cover linking, rank milestones, completed seasons, lifetime kills/wins/playtime and Challenge Club victories. Medals are recognised when a profile/dashboard is loaded, from saved source stats and history. Earned medals persist in the same database across seasons and subsequent stat reductions. Existing history can qualify; recognition dates are not original achievement dates. Medals do not change ELO or grant Discord roles. These medals appear on website profiles; existing Discord embeds are unchanged.

### Performance graphs

Your own profile has improved rating charts plus kills/deaths, wins/losses, K/D and win-rate graphs. All share the 7-day, 30-day and current-season filters. Charts include labelled axes, distinct line styles, point hover details, and accessible exact-value tables.

Combat trends use recorded scoring deltas, grouped by their recorded UTC date. Pauses, missing feeds and unrecorded history are not reconstructed. They are not match history or a complete record of every day played. K/D is unavailable when recorded deaths are zero; win rate is unavailable without recorded outcomes. Medals can use lifetime stats, while trends use scoring history. Demo mode remains illustrative and never changes a wallet or posts a challenge.

Verification: 182 automated tests passed; browser checks cover challenge terms, graph periods, medals and responsive layouts. Live OAuth, Discord publishing and real-feed settlement require deployment verification on your server.
