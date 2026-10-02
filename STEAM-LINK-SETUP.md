# Automatic Steam linking with /link

Members no longer need to type a Steam ID or ask an administrator to enroll them manually. `/link` opens Steam's official sign-in flow, obtains the verified SteamID64, and asks the initiating member to confirm that profile back in Discord. New members then enter progression at Private / 0 using a fresh leaderboard baseline. Existing ratings are preserved.

This uses Steam OpenID. Steam passwords and Steam Guard codes are entered only on **steamcommunity.com**, never in the bot or its callback page. No Steam Web API key, Steam client secret, or extra Discord OAuth secret is needed for this implementation.

## Install on Railway

1. Extract **22a-steam-link-update.zip**.
2. Upload **bot.py**, **leaderboard.py**, **progression.py**, and **steam_link.py** to the top level of your existing GitHub repository. Replace older copies and commit.
3. Keep your existing bot variables, token, leaderboard settings, and persistent database volume. Rank progression must already be enabled through `RANK_ANNOUNCEMENT_CHANNEL_ID`. Run `/ranks-setup` if you have not created the rank roles yet.
4. Open your Railway bot service → **Settings → Networking → Public Networking → Generate Domain**. Use its HTTPS domain, such as `https://your-service.up.railway.app`. Set the domain's **target port to 8080**.
5. Add these Railway variables, replacing the example URL with the actual generated domain:

```dotenv
PORT=8080
STEAM_LINK_BASE_URL=https://your-service.up.railway.app
```

The URL must be just the HTTPS origin: no `/steam/callback`, other path, query string, or Railway project-dashboard URL. Do not paste the example hostname literally. If you use a different port, both `PORT` and the domain target port must match.

6. Deploy the changes. Keep the start command **python bot.py**. The small sign-in callback server runs in the same process as the Discord bot.
7. Visit `https://YOUR-ACTUAL-DOMAIN/health`. It should display **22A Steam linking service**. This checks HTTP reachability, not Discord permissions or completion of a Steam login.
8. In Discord, run `/link` and complete the process below. If the command is absent, check the bot log, configured guild, and both required variables, then refresh Discord. The command is registered only when sign-in is enabled.

Railway supplies HTTPS termination; the Python service listens on its internal port. You do not need to buy a domain or register a redirect in Discord's Developer Portal for this Steam-only flow. Keep one bot instance running. Do not open a second local instance while the Railway bot is active.

Official Railway reference: [Domains and target ports](https://docs.railway.com/networking/domains/working-with-domains).

## What a member does

1. Run **/link** in your Discord server. The response is private to that member.
2. Select **Sign in through Steam**. Complete login on Steam's own website in the same browser.
3. The callback page says **Steam account verified**. Return to the original Discord message.
4. Select **Review Steam account**. Check the displayed Steam profile is yours.
5. Select **Confirm link** in the new private message.
6. Use **/rank** to check progression. A new enrollment gets Private / 0; existing progression is not reset.

The review and confirmation are deliberate: opening a link or signing in does not by itself attach an account to a Discord member. The member who issued `/link` must confirm it in Discord.

A verified Steam account can link even when the public leaderboard is stale or the player has not appeared yet. The new account is saved at Private / 0 with a waiting status. The first fresh all-time WDUK snapshot containing the player becomes the baseline and awards no historical points. Later changes earn rating. Steam identity verification does not verify ownership of WarDogs itself.

## Existing accounts and leaderboard mentions

- New enrollment uses **/link** only. The manual rank-link command has been removed.
- Members manually linked earlier can use `/link` to verify the same Steam account. Their score, baseline, rank, pause state, and review holds remain unchanged.
- A Steam account can belong to only one saved Discord identity, and vice versa. `/link` cannot overwrite a different pairing or reset a rating. Identity corrections still require an administrator's deliberate review.
- Steam-verified, active progression accounts automatically supply Discord mentions to the player leaderboard at its next refresh. No edits to `leaderboard-links.json` are needed for those accounts. Manual leaderboard mappings continue to work.
- Paused/held rank accounts are not silently resumed by linking. An administrator uses `/rank-resume` after review as described in `RANKS-SETUP.md`.

## Troubleshooting and security behaviour

- **Link expired / restart:** links last 10 minutes and pending sign-ins are kept in memory. A restart invalidates them; run `/link` again. Completed links and ratings are stored in SQLite and persist.
- **Wrong browser / cookie:** complete the Steam login in the browser that opened the link. The callback checks a secure browser cookie. If an embedded Discord browser gives trouble, open the original link in a regular browser and finish there.
- **Wrong Steam account:** do not confirm. Switch accounts on Steam and start a new `/link`; the new request invalidates your previous pending link.
- **502 / health unavailable:** verify the public domain targets the same port as `PORT`, the base URL matches it, and the deployment is running. Inspect the bot log for missing variables or a port conflict.
- **Cannot assign role:** check Manage Roles and the bot's role hierarchy. Registration is saved before role assignment; retrying does not reset it. The rank worker retries saved role work.
- **Steam unavailable:** no unverified link is accepted; retry when Steam is available. **Stats unavailable:** verified linking still completes. Rating remains at zero while the bot waits for a fresh baseline. Existing players retain their ratings and freshness protection.
- Pending links are secret, short-lived URLs. Do not share them. The app disables request access logging and uses no-referrer/no-store responses. External reverse-proxy access logs may still contain URLs; keep hosting logs private.
- Verification checks the fixed Steam provider, signed return URL, claimed identity, signed fields, recent response nonce, browser cookie, duplicate query parameters, and Steam's direct signature-verification response. Responses cannot be replayed into another pending account. Final Discord confirmation binds completion to the initiating member.
- At most 500 pending sign-ins are kept; each Discord member has one current link. New `/link` requests replace the previous one. Do not run multiple replicas: pending sign-ins are process-local, and the main bot/database already requires a single instance.
- To disable self-service linking, clear `STEAM_LINK_BASE_URL` and redeploy. Saved identities/ratings remain, but new enrollment is unavailable until Steam sign-in is enabled again.

## Local hosting

The callback requires a public HTTPS origin. Running only the launcher on a PC with no public HTTPS routing is insufficient. The supported instructions here are for Railway; a local deployment would need a correctly configured HTTPS reverse proxy/tunnel to the configured `PORT`. Do not use an HTTP URL or turn off cookie/TLS checks to work around that requirement.

## Validation

All 66 offline tests passed, including identity binding, confirmation ownership, replay rejection, secure-cookie behaviour, expired sessions, pinned Steam verification, existing-rating preservation, and the previous rank/squad/leaderboard tests. Steam responses are simulated in the sign-in tests. A real end-to-end Steam login has not been completed during development; test one account on your deployed HTTPS domain before inviting everyone to link.

Official Steam reference: [Browser authentication with OpenID](https://partner.steamgames.com/doc/features/auth#website).


