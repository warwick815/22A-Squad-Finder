# 22A — WarDogs Squad Bot

A ready-to-configure Python Discord bot based on the reference's **Looking For Squad** embed and three permanent buttons. Built for one 22A server per running instance. Python **3.11 or newer** is required; verified locally with Python 3.12 and discord.py 2.7.1.

## What you get

**Member website:** See [WEBSITE-SETUP.md](WEBSITE-SETUP.md) for the Railway-hosted 22A hub with Discord sign-in, profiles, standings, comparisons and speciality selection. Uses the existing database and includes the green/purple 22A logo theme.

**Player Hub:** See [PLAYER-PANEL-SETUP.md](PLAYER-PANEL-SETUP.md) for My Profile / Link Steam / Rank Guide buttons, private game-stat profiles, and emoji rank badges.

**Optional /link:** See [STEAM-LINK-SETUP.md](STEAM-LINK-SETUP.md) for self-service Steam verification and rank enrollment through a public HTTPS callback.

**Optional rank progression:** See [RANKS-SETUP.md](RANKS-SETUP.md) for the Private-to-WO1 community rating system, cosmetic roles, and promotion/demotion announcements.

**Optional live leaderboard:** See [LEADERBOARD-SETUP.md](LEADERBOARD-SETUP.md) to add a five-minute, self-updating WDUK stats embed with Kills / K/D / Deaths / Hours / Cash buttons. Uses the same bot and token; disabled until a leaderboard channel is configured.

- A red-accented, 22A-branded permanent panel: **Create WarDogs Squad**, **Create Other Game Squad**, **Create Private Channel**.
- Modals collect the squad name, maximum players, notes, and other game's name.
- Public squad adverts show the leader, roster, capacity, recruiting/locked/full status, and private voice channel.
- **Join Squad / Leave Squad / Join Voice / Leader Controls** buttons.
- Joining grants private voice access and moves you if you are already in voice. Discord cannot make a disconnected user connect; otherwise the bot provides a clickable channel mention.
- Leader controls: rename, lock/unlock recruitment, invite, kick, transfer leadership, and confirm disband. People with **Manage Server** can also manage rooms.
- Private rooms have **no public advert**. Their owners use `/room` to invite friends and manage access.
- Maximum roster size is enforced atomically; voice capacity matches it. Creation is limited to one owned room per person and a configurable server-wide room count. Automatic succession after a leader leaves can give a member more than one room; `/room room_id:...` addresses each.
- SQLite saves the panel ID, rooms, owners, member access, voice IDs, adverts, lock state, and cleanup timers. Permanent buttons survive restarts. Temporary control menus expire after a few minutes; reopen `/room` or Leader Controls.
- Automatic cleanup and retry of failed Discord operations. No token is included in the project.

The screenshot's Steam linking is not included in this brief. There is no Steam account integration. Add your own 22A logo URL if desired; the reference community's artwork is not bundled.

## 1. Create the application and bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), sign in, select **New Application**, and name it `22A Squad Finder`.
2. Open **Bot**. If prompted, choose **Add Bot**. Set the bot's display name/avatar as desired.
3. Under **Privileged Gateway Intents**, enable **Server Members Intent**. Leave **Presence Intent** and **Message Content Intent** off; this bot does not need them. Member events are used to remove people who leave the server. If Discord requires approval for your app's privileged intent access, obtain it before running.
4. Under **Token**, choose **Reset Token** if needed and copy it directly into your local `.env` file as `DISCORD_TOKEN`. The token is a secret. Do not paste it into chat, source code, screenshots, or public repositories. If exposed, reset it in the portal.
5. Leave **Requires OAuth2 Code Grant** disabled.

## 2. Invite it with the required permissions

1. In **Installation**, enable **Guild Install** (server installation). If shown, select **Discord Provided Link**.
2. In **OAuth2 → URL Generator**, choose scopes **bot** and **applications.commands**. Choose Guild Install as the integration type if a selector appears.
3. Select these bot permissions:

   | Group | Permission |
   | --- | --- |
   | General | View Channels, Manage Channels, Manage Roles |
   | Text | Send Messages, Embed Links, Read Message History |
   | Voice | Connect, Speak, Video, Use Voice Activity, Move Members |

   Discord may label Video as Stream. Manage Roles is needed to edit per-member channel permission overwrites. Move Members supports moving connected users and disconnecting kicked users. Administrator is **not required**.
4. Open the generated URL, select your 22A server, and authorize the bot. Your installing account needs Manage Server.
5. In **Server Settings → Roles**, ensure the bot's role has those permissions. Keep the bot role above any special member roles it needs to manage if your server's role setup restricts operations. Channel/category permission overrides must also allow the bot to operate.

## 3. Prepare the server and copy IDs

1. Create a normal text channel such as `#lfg-and-private-voice`. Let community members view it, read message history, and use application commands. You can prevent ordinary members from posting messages to keep the adverts tidy.
2. Create a category such as `22A — TEMP SQUAD VOICE`, preferably dedicated to these temporary rooms. Leave space for new channels; Discord limits a category to 50 children. The default bot limit is 30 rooms.
3. Explicitly allow the bot's role the permissions above in the text channel and category. Do not remove the bot's access after it has created rooms.
4. In your Discord client, enable **User Settings → Advanced → Developer Mode**.
5. Right-click the server icon → **Copy Server ID**; put it in `GUILD_ID`.
6. Right-click the LFG text channel → **Copy Channel ID**; put it in `LFG_CHANNEL_ID`.
7. Right-click the temporary voice category → **Copy Channel ID**; put it in `VOICE_CATEGORY_ID`.

The bot explicitly builds each voice room's permissions: everyone is denied View/Connect, roster members are allowed, and the bot retains management access. It does not inherit other category roles' voice access. **Discord Administrators always bypass private-channel permissions and capacity restrictions**. Locking prevents new roster joins/invites; existing members can reconnect. Kicking removes membership and disconnects the user, but does not ban them from rejoining an unlocked public squad.

## 4. Configure and run on Windows

Install Python 3.11+ from [python.org](https://www.python.org/downloads/) if necessary. Extract the ZIP, open PowerShell in the extracted `22a-squad-bot` folder, then run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Fill in the token and three IDs. Save and close Notepad. Then:

```powershell
.\.venv\Scripts\python.exe bot.py
```

Using the virtual environment's Python directly avoids PowerShell script execution-policy issues. If your system uses `python` instead of the `py` launcher, replace the first `py -3` with `python`.

## 5. Configure and run on Linux/macOS

In the extracted project folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your editor, then run:

```sh
.venv/bin/python bot.py
```

On Linux, your distribution may require its `python3-venv` package. Commands do not need activation of the virtual environment. Environment variables supplied by a hosting service override `.env` values.

## First launch and daily use

When startup succeeds, the log says `22A ready`, the bot appears online, and it automatically posts the permanent panel in the configured LFG channel. Commands are synced directly to the configured server. Refresh Discord if the new commands are not immediately visible.

| Action | How |
| --- | --- |
| Post or repair the panel | `/panel` — requires Manage Server; edits the existing panel rather than duplicating it |
| Start a WarDogs squad | Panel → Create WarDogs Squad → fill in the modal |
| Start another game | Panel → Create Other Game Squad → include the game name |
| Join a squad | Advert → Join Squad; already-connected users are moved automatically if allowed |
| Get the voice channel | Advert → Join Voice; join the squad first |
| Leave a squad | Advert → Leave Squad; access is revoked and connected users are disconnected |
| Create a private room | Panel → Create Private Channel; it creates no advert |
| Manage a room | Leader Controls or `/room` |
| Invite a friend to a private room | `/room` → Invite member → choose a server member; let them know to join the now-visible room |
| Leave a private room | `/leave-room room_id:...` using the room ID supplied by the owner from /room |
| Administer a specific room | `/room room_id:...` using the room ID from the advert footer or owner controls |

An ID looks like `a1b2c3d4e5f6`. Voice channels show only the chosen name, e.g. `Alpha`. A temporary recovery prefix may appear briefly during creation; it is removed once the channel ID is saved. Existing tracked channels are renamed automatically after updating. Internal room IDs remain in advert footers and owner controls. Use the bot controls to rename rooms so the saved name is updated too.

Invite grants access without sending a DM. A private room's unlocked state still only permits explicitly invited users. Leader transfer requires an existing room member who does not already own another room. Leaving automatically promotes the next member in join order. Disbanding deletes the room and advert, including when users are connected.

## Cleanup and restart behaviour

- A newly created room gets **10 minutes** for someone to enter voice.
- Once used, an empty voice room gets **2 minutes** before deletion, even if its roster still contains members. Being listed in an advert does not keep an empty voice channel alive.
- Cleanup checks run every **30 seconds**, so deletion can occur up to roughly 30 seconds after the timeout, plus API delays.
- Re-entering voice cancels the empty timer. Leaving the final roster slot or disbanding removes the room immediately.
- On restart, saved rooms are restored and empty rooms receive a fresh grace period. Occupied rooms are retained. The bot rechecks saved members and reapplies permissions.
- If an admin deletes a voice room, the matching advert is cleaned up. Deleted adverts are recreated for existing active squads. If the panel is deleted while the bot runs, use `/panel` to restore it (or restart).
- Failed changes retain their saved desired state and are retried. Permission errors are logged; fix permissions so the next sweep can finish. A failed creation can reserve the owner's room slot until the bot successfully retries it.
- A crash immediately after sending an advert is recovered by searching the last 200 LFG messages. An unusually busy channel can exceed this recovery window and leave a duplicate advert; remove the older duplicate manually. The panel has a similarly small send/save crash window; keep the recorded panel and remove a stray copy if needed.

## Configuration reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `DISCORD_TOKEN` | required | Bot token; loaded only from environment or `.env` |
| `GUILD_ID` | required | Your server's numeric ID |
| `LFG_CHANNEL_ID` | required | Normal text channel for panel/adverts |
| `VOICE_CATEGORY_ID` | required | Category for generated voice channels |
| `EMPTY_TIMEOUT_SECONDS` | `120` | Used-room empty grace; minimum 30 |
| `INITIAL_TIMEOUT_SECONDS` | `600` | Never-used room grace; minimum 60 |
| `MAX_SQUAD_SIZE` | `16` | Maximum allowed modal capacity; 2–25 |
| `MAX_ACTIVE_ROOMS` | `30` | Server room limit; 1–45; leave category headroom |
| `DATABASE_PATH` | `data/22a.sqlite3` | Persistent SQLite file, relative to the project or absolute |
| `BRAND_LOGO_URL` | blank | Optional public HTTPS image URL for your own logo |

Restart after changing configuration. The database is bound to the server/text/category ID combination to prevent accidental cross-server cleanup. To migrate channels, first disband old rooms, then change the IDs and use a fresh database path. Preserve old databases until migration is verified.

## Hosting and backups

The bot runs only while its Python process is running and the host has internet access. Keep the terminal open for local testing. For continuous use, run it on an always-on host with a process supervisor configured to restart on failure. It uses Discord's outbound gateway/API connections; no public website, webhook endpoint, or inbound port is needed.

Run **one process per database/server setup**. Multiple instances are not supported. Keep the `data` folder on persistent storage, outside any ephemeral deployment filesystem. To back up, stop the bot cleanly with Ctrl+C and copy the `data` folder; also keep a secure copy of your configuration. Do not delete the database while active rooms exist: it is the ownership record used for safe cleanup. Server member IDs and room details are stored locally. Deleted room records are removed from the database.

## Troubleshooting

- **Configuration error:** replace the placeholder IDs with digits and set the token in `.env`. The script finds `.env` beside `bot.py`, regardless of your current directory.
- **LoginFailure / improper token:** reset/copy the bot token from the Bot page, not the application ID or client secret. Never share the token in logs or support requests.
- **PrivilegedIntentsRequired:** enable Server Members Intent in the portal (and get approval if required).
- **403 / Missing Permissions:** recheck bot role and channel/category overrides. Overwrite edits require Manage Roles; channel creation/deletion requires Manage Channels. Check Move Members, Connect, and permissions in the source voice channel if automatic movement fails.
- **Startup says wrong channel type:** use a normal text channel ID and a category ID, not a thread, forum, stage channel, or voice-channel ID.
- **Buttons do not respond:** check that the bot is online and logs show readiness. Reopen expired leader controls. Persistent panel/advert buttons do not expire.
- **Room stays around after timeout:** anyone still connected, including bots/admins, counts as occupancy. Otherwise inspect cleanup error logs and permissions.
- **Room gets deleted although people joined the advert:** they must enter voice before the initial timeout. Increase the timeout if your community assembles slowly.
- **No logo:** leave the optional URL blank or use a publicly accessible HTTPS image URL.

## Validation

Run the included offline tests after installing requirements:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux/macOS use `.venv/bin/python` instead. Tests exercise capacity/lock rules, leader succession, durable records, persistent UI registration, permissions, crash recovery, deletion retries, and empty/occupied cleanup. They use simulated Discord API calls, not a live server.

Before using it in your main community, verify in a test channel with two Discord accounts:

1. Create each type of room; confirm private rooms have no advert.
2. Confirm a nonmember cannot see/connect to the voice room (use an account without Administrator).
3. Join, fill capacity, leave, invite, lock/unlock, kick, rename, and transfer leadership.
4. Restart the bot with a squad open; test its original buttons and membership access.
5. Let an empty room expire, disband an occupied room, and delete a voice room manually; confirm the matching advert disappears.
6. Remove and restore a required bot permission; check that saved operations retry without losing the room record.

Live Discord operation was not tested with your server or credentials. Offline verification cannot establish your server's permissions or Discord client behaviour.

## Official references

- [discord.py persistent view example](https://github.com/Rapptz/discord.py/blob/master/examples/views/persistent.py)
- [discord.py interactions, views, and modals](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [Discord permissions](https://docs.discord.com/developers/topics/permissions)
- [Discord gateway intents](https://docs.discord.com/developers/events/gateway)
- [Discord OAuth2 installation](https://docs.discord.com/developers/topics/oauth2)


## Member HQ v2 website

Includes the redesigned dashboard, rating charts, sortable standings, archived seasons, squad membership, profile sharing and staff operations. See [WEBSITE-SETUP.md](WEBSITE-SETUP.md) for installation and limits. Existing Railway variables and player database are preserved during deployment.
