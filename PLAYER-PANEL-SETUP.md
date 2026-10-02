# 22A Player Hub and private profiles

## Install

1. Extract **22a-player-panel-update.zip**.
2. Upload all five Python files into your existing GitHub repository: **bot.py**, **leaderboard.py**, **progression.py**, **steam_link.py**, and **player_panel.py**. Replace older copies and redeploy on Railway.
3. Keep your existing variables and persistent database. No new dependencies are required. Progression must be enabled with `RANK_ANNOUNCEMENT_CHANNEL_ID`.
4. The hub automatically appears in the rank-announcement channel. To put it elsewhere, run **/player-panel channel:#player-hub** as an administrator with Manage Server.
5. Give the bot View Channel, Send Messages, Embed Links and Read Message History in that channel.
6. Run **/ranks-setup** once to add badges to existing default rank role names. Recorded role IDs and ratings remain unchanged; custom names are preserved.

For local use, stop the bot, copy the same five Python files into its folder, and restart with your launcher. Keep `.env`, `.venv`, and `data` unchanged.

## Buttons

- **My Profile:** private response showing the clicking member's Discord avatar, Steam link, rank badge, rating, next promotion progress bar, points needed, demotion boundary, scoring status and any review hold.
- **Link Steam:** the existing verified Steam sign-in flow; requires the working `STEAM_LINK_BASE_URL` configuration. This does not bypass login verification.
- **Rank Guide:** the scoring, promotion ladder and demotion rules, shown privately.

Profiles also show all-time WDUK kills, deaths, K/D, wins, losses, calculated win rate, hours, cash earned, kills per hour, team kills, suicides, most played server, last seen, and game presence at the source snapshot. These are lifetime game totals; progression still counts only results after enrollment. Missing fields show a dash. Cached data over 15 minutes old is marked clearly. An unlinked player is prompted to link first.

## Badges

| Rank | Badge |
| --- | --- |
| Private | 🪖 |
| Lance Corporal | 🔰 |
| Corporal | ⚔️ |
| Sergeant | 🛡️ |
| Staff Sergeant | 🎖️ |
| Warrant Officer Class 2 | ⭐ |
| Warrant Officer Class 1 | 👑 |

These are community badges, not official British Army insignia. They appear in profiles, `/rank`, guides, daily standings and rank announcements. New role names include them; `/ranks-setup` upgrades existing default names. Unicode emoji require no server boosts or custom role-icon support. Appearance varies by device.

## Persistence and refresh

The bot stores the panel message ID, edits it across restarts and recreates deleted panels at the next five-minute check. Moving the panel leaves the old copy for an admin to delete. Optional `PLAYER_PANEL_CHANNEL_ID` overrides its saved destination; leave it unset when using the command to choose a channel. Crash recovery scans the last 100 messages; a very busy channel can exceed that window and permit a rare duplicate after a crash.

Profiles use the existing progression feed fetch, with no extra website request per click. Successful fetches cache linked players' stats in the same SQLite database. The full public feed may be held in memory, but only linked players' rows are saved to disk. Rank setup must be valid for regular progression fetches. A newly linked account may need to wait until the next successful five-minute refresh. The saved rank/rating still appears while game stats are unavailable.

A private profile is a snapshot when opened. Press My Profile again for refreshed data. Existing commands, ratings, daily standings and other bot features remain available.

All 77 offline tests passed, including profile privacy, all rank layouts, embed size limits, missing data, cache persistence and persistent buttons. Verify a linked player's profile in your Discord after deployment; no live server changes were made during development.
