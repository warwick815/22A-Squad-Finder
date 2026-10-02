# Top 10 Clans — add a second leaderboard embed

This update adds a separate **Top 10 WarDogs Clans** message to your existing bot. Your player leaderboard and squad features remain available. It uses the public WDUK clan feed, polls every five minutes, and edits its own saved message instead of posting a new one each time.

## GitHub / Railway installation

1. Extract `22a-clans-update.zip`.
2. Open your existing GitHub bot repository → **Add file → Upload files**.
3. Upload the update's **bot.py** and **leaderboard.py** into the repository's top level, replacing those two existing files. Commit the changes.
4. In your Railway bot service's **Variables**, add:

```dotenv
CLAN_LEADERBOARD_CHANNEL_ID=YOUR_DISCORD_TEXT_CHANNEL_ID
CLAN_LEADERBOARD_PERIOD=all
```

5. Use the same numeric channel ID as `LEADERBOARD_CHANNEL_ID` to put the clan embed alongside the player embed. Alternatively, copy a different text channel's ID from Discord with Developer Mode enabled. The bot needs **View Channel**, **Send Messages**, **Embed Links**, and **Read Message History** there.
6. Apply/deploy the changes. If automatic deployment is disabled, deploy the latest commit manually. Keep only one bot instance running.

The second embed appears after the bot starts and fetches the feed. No new token, database, dependency, or Discord application is needed. Keep your existing variables and persistent database volume.

## Local installation

Stop the bot, replace **bot.py** and **leaderboard.py** in the existing bot folder, append the two settings above to your existing `.env`, and restart using your launcher. Keep `.env`, `.venv`, and `data`; do not replace or remove them. Upload neither your token nor `.env` to GitHub.

## Display and behaviour

- Top **10 clans across the whole WDUK clan feed**, not just names containing 22A. The player filter does not affect clans.
- Starts with **all-time kills**, matching your screenshot. Buttons switch between Kills, K/D, Deaths, Hours, and Cash. The selected stat is saved independently of the player leaderboard.
- Displays clan tag, member count, kills, deaths, K/D, hours, and earned cash. A star highlights **22A** when it is in the selected top 10. It does not insert 22A if it ranks outside that top 10.
- Ties use shared ranks; equal values are ordered by tag for a stable display. If the source publishes fewer than 10 clans, all available clans are shown. Exceptionally long source entries may reduce the number shown to stay within Discord limits.
- Set `CLAN_LEADERBOARD_PERIOD` to `all`, `weekly`, or `daily`. Restart/redeploy after changing it. The player period is configured separately.
- Both embeds can occupy the same text channel. Their message IDs, cached results, stat selections, refresh tasks, and button IDs are separate. Clicking one does not change the other.
- The message shows the source timestamp and last successful fetch time. A failure retains cached data with a warning; source data older than 15 minutes is labelled stale. Feed availability and publication frequency are controlled by wardogs.uk.
- Deleting the message recreates it at the next refresh. Restarting reuses its saved message. Keep the existing SQLite database on persistent storage.
- Clearing `CLAN_LEADERBOARD_CHANNEL_ID` and restarting disables clan updates. The old message remains until you delete it. Changing channel IDs posts in the new channel; remove the old post manually if no longer wanted.

Source: [WDUK leaderboard](https://wardogs.uk/leaderboard.html), using its public `leaderboard-clans-all.json` feed (or the weekly/daily equivalent). This covers clans recorded on WDUK servers, not a global ranking across all WarDogs servers.
