# Add the live 22A leaderboard to your existing bot

For an additional **Top 10 Clans** embed, see [CLAN-LEADERBOARD-SETUP.md](CLAN-LEADERBOARD-SETUP.md). It can share the player leaderboard's channel and updates independently every five minutes.

You do not need another Discord application or token. This update adds a leaderboard to the existing 22A squad bot and preserves its squad features and saved room records.

## Install the update

1. Stop the bot with **Ctrl+C**. If using the launcher, keep it stopped until the files are replaced.
2. Extract `22a-leaderboard-update.zip` and copy **bot.py** and **leaderboard.py** into your existing bot folder, beside `config.py` and `state.py`. Replace the old `bot.py`. Keep your existing **.env**, **data** folder, and **.venv** unchanged.
3. Create a normal Discord text channel such as **#22a-leaderboard**.
4. In that channel's permissions, allow the bot **View Channel**, **Send Messages**, **Embed Links**, and **Read Message History**. Allow your members to view/read the channel. You can prevent ordinary messages to keep it tidy; members can still use the embed buttons.
5. Enable Discord **User Settings → Advanced → Developer Mode** if needed. Right-click the new text channel and choose **Copy Channel ID**.
6. Open your existing `.env` and append the following, replacing the first value with the copied channel ID:

```dotenv
LEADERBOARD_CHANNEL_ID=PASTE_CHANNEL_ID_HERE
LEADERBOARD_FILTER=22A
LEADERBOARD_PERIOD=all
LEADERBOARD_TOP=20
```

7. Save `.env` and start the bot with your existing launcher, or run:

```powershell
.\.venv\Scripts\python.exe bot.py
```

The bot should post the leaderboard shortly after successful startup. Subsequent refreshes edit that same message every five minutes. No extra dependency installation is needed for an existing installation: the HTTP client is already installed with discord.py.

If you use Railway later, enter these settings under **Variables** instead. Include `leaderboard.py` in the deployed project. The existing SQLite database on persistent storage also saves leaderboard state.

## What the message shows

- A **22A — WarDogs Leaderboard** embed with a red accent and optional 22A logo.
- Medal/rank, player name, and the selected stat, laid out similarly to your reference image.
- Five buttons: **Kills**, **K/D**, **Deaths**, **Hours**, **Cash**. Clicking changes the shared message for everyone. The selection is remembered on restart. Buttons use cached data; they do not trigger extra website requests. There is a three-second shared click cooldown.
- A green dot when the public feed says the player is online. This is game/server presence at the source snapshot time, not Discord presence.
- The website's data timestamp and the last successful fetch time. Refreshing the embed cannot make the website publish newer stats.
- Up to 20 players, ranked within the matching names. Ties share the same rank. Very long entries may reduce the number shown to fit Discord's embed size limit.

The default **22A** filter matches your first screenshot's search, including any unrelated name that happens to contain those characters. To require the visible clan tag, set `LEADERBOARD_FILTER=[22A]`. To show the entire public leaderboard, set `LEADERBOARD_FILTER=` with nothing after the equals sign. Set `LEADERBOARD_PERIOD` to `all`, `weekly`, or `daily`; the default is all-time. Restart after changing settings.

This reads stats recorded by the WDUK servers and published on wardogs.uk. It does not provide stats for servers or players absent from that feed. The website's global rank numbers differ from ranks within the filtered 22A list.

## Discord mentions versus Steam links

The public feed supplies Steam IDs and names, but **does not supply Discord user IDs or the other community's Steam account links**. By default, player names link to their Steam profiles. No Steam sign-in is required, and no claim is made that players have verified their accounts with your bot.

For Discord mentions like your reference image, optionally create **leaderboard-links.json** beside `bot.py`. Its format is a JSON object whose keys are SteamID64 strings and values are Discord user ID strings. For example, using illustrative IDs only:

```json
{
  "76561198000000000": "123456789012345678"
}
```

Replace both values with the real, confirmed pair. To get a Discord user ID, enable Developer Mode, right-click that member, and choose Copy User ID. The Steam profile links in the embed contain each player's SteamID64. Confirm ownership with the member before associating identities. Do not infer links from matching display names.

Restart after editing this file. Mapped players show a Discord mention and their in-game name. Unmapped players keep their Steam link and are still included. The bot suppresses mention notifications. This is a manual administrator-maintained mapping, not Steam OAuth or an account-verification system.

To add your logo, use your existing `BRAND_LOGO_URL` setting with a public HTTPS image URL. It also updates the squad panel's thumbnail.

## Persistence, failures, and limits

- The message ID, selected stat, and a compact last-successful snapshot are saved in the existing SQLite database. Keep the database across hosting updates.
- Restarting updates the saved message. If it is deleted, the bot recreates it on the next cycle.
- If the feed fails or changes format, the bot keeps the previous results and displays a warning. It retries in five minutes. If no successful snapshot exists, it posts a waiting message.
- A source timestamp over 15 minutes old is labelled as stale.
- Missing channel permissions are logged and retried without stopping the squad bot. Set an actual numeric channel ID; invalid configuration is reported at startup.
- Changing the leaderboard channel creates a post in the new channel; the old post is not deleted automatically. Delete the old post yourself if no longer wanted. Clear `LEADERBOARD_CHANNEL_ID` and restart to disable this feature; any existing message remains as an inactive snapshot.
- The source is the website's public JSON feed, not a guaranteed supported API. Its format or access rules may change. This integration uses one request per five-minute cycle and preserves source attribution.
- A send/save crash recovery search scans the last 100 messages for the bot's leaderboard marker. A very busy channel can exceed that window and leave a duplicate after an unusual crash; keep the active one and remove the duplicate.
- Run only one bot process for this setup.

## Verification completed

The actual public feed was fetched successfully using the same HTTP code used by the bot. At verification time, `22A` matched 10 players. All 30 offline tests passed, covering the original squad features plus feed decoding, filtering, sort buttons, embed limits, message reuse/recreation, cache persistence, and failed-fetch handling.

The update has not been posted to your Discord server during development. After installation, confirm the first message appears, try all five buttons, restart the bot to check message reuse, and allow a five-minute cycle to complete.

Source: [WDUK public leaderboard](https://wardogs.uk/leaderboard.html).
