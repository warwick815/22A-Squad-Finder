# 22A rank progression

**Self-service option:** See [STEAM-LINK-SETUP.md](STEAM-LINK-SETUP.md) to let members use `/link` with verified Steam sign-in instead of administrator enrollment.

This adds team-weighted community ratings, cosmetic British Army soldier-rank roles, and promotion/demotion announcements to the existing squad/leaderboard bot. It is a community scoring system, not matchmaking Elo or an official Army progression system.

## Install on GitHub / Railway

1. Extract **22a-ranks-update.zip**. Upload **bot.py**, **leaderboard.py**, and **progression.py** to the top level of your existing GitHub repository; replace older copies. Commit the changes.
2. Create a text channel such as **#promotions-and-demotions** in Discord. Give the bot View Channel, Send Messages, Embed Links, and Read Message History there.
3. Add this Railway variable, replacing the placeholder with that channel's numeric ID:

```dotenv
RANK_ANNOUNCEMENT_CHANNEL_ID=YOUR_CHANNEL_ID
```

4. Keep your existing variables and persistent database volume. Deploy the update. Run only one bot instance.
5. In Discord, as a member with **Manage Server**, run **/ranks-setup**. It creates the seven cosmetic roles. The bot needs **Manage Roles**, and its highest role must be above all seven new roles.
6. Configure Steam sign-in using STEAM-LINK-SETUP.md. Each member then runs **/link**, signs in through Steam, and confirms their account in Discord.
7. That member receives **Private**, starts at **0 rating**, and their current counters become their baseline. Repeat the linking step for each participating member. Members can use **/rank** to check their progress.

Members enroll themselves through verified Steam sign-in. Existing saved links and ratings are preserved, including previously admin-linked accounts. Manual leaderboard mappings are not automatically imported. New accounts wait at Private / 0 for their first fresh baseline; historical results never award points.

For a local installation, stop the bot, copy the same three Python files beside `config.py` and `state.py`, append the variable to your existing `.env`, and restart with your launcher. Keep `.env`, `.venv`, and `data`. Never upload your token or `.env` to GitHub. No new dependencies or bot token are required.

## Agreed scoring

Only increases after the saved baseline count. This scoring update preserves existing ratings and baselines; it applies to subsequently processed stat deltas (including any unprocessed results since the last saved snapshot), without recalculating historical ratings. Promotion thresholds and demotion buffers are unchanged:

| Result | Rating |
| --- | ---: |
| Win | +30 |
| Loss | −10 |
| Kill | +2 |
| Death | −1 |

Example: 2 wins, 1 loss, 30 kills and 20 deaths gives **+90 points**. A win/loss weighs much more than an individual kill/death; sufficiently large combat totals can still outweigh a team result because this formula has no combat cap. K/D is represented through kills versus deaths rather than a second lifetime-ratio bonus. Team kills are not separately scored.

Rating never falls below zero. No points are removed for inactivity. All linked players start at Private regardless of their previous stats. Changes are checked every five minutes using the all-time public feed, regardless of the display leaderboard's chosen period or name filter. A snapshot, not the exact second of enrollment or an individual match result, is the scoring boundary.

## Initial rank thresholds

These are starting balance settings for your community, not official Army requirements.

| Rank | Promote at | Demote when below |
| --- | ---: | ---: |
| Private | 0 | Never |
| Lance Corporal | 250 | 200 |
| Corporal | 750 | 700 |
| Sergeant | 1,500 | 1,450 |
| Staff Sergeant | 3,000 | 2,950 |
| Warrant Officer Class 2 | 5,000 | 4,950 |
| Warrant Officer Class 1 | 8,000 | 7,950 |

A player at exactly 200 keeps Lance Corporal; 199.5 demotes them. The 50-point buffer avoids frequent role switching around a threshold. A large update can cross several ranks; one announcement shows the original and final ranks. The top rank retains accumulating points.

Rank names follow the [British Army soldier rank structure](https://www.army.mod.uk/learn-and-explore/ranks). Officer ranks are not included in this version. The thresholds live in `RANKS` in `progression.py`; ask for a balancing update before editing live settings, because changed thresholds can affect later rank evaluations.

## Roles and announcements

### Permanent player guide

The bot now automatically posts a **22A — Rank Progression** guide in the rank announcement channel, even before members enroll. It explains linking, the scoring formula, promotion thresholds, demotions, and update timing. It uses `/link` instructions when Steam sign-in is configured, otherwise instructions to ask an admin to enable Steam sign-in.

To place it elsewhere, an admin can run **/rank-guide channel:#rank-info**. With no channel argument, `/rank-guide` repairs the saved guide in its existing channel. The bot remembers the message and edits it rather than repeatedly posting new copies. A deleted guide is recreated within the next five-minute check. Moving it to a different channel leaves the old copy for an admin to remove. Optional `RANK_GUIDE_CHANNEL_ID` overrides the saved guide destination on automatic checks; leave it unset when using the command to choose a channel. The selected channel needs View Channel, Send Messages, Embed Links, and Read Message History for the bot.

To install just this feature over the current progression version, replace **progression.py** in GitHub and redeploy. No new variables are required. The feature still requires rank progression itself to be enabled and the bot to start successfully.

- Roles are named `22A Rank • Private`, `22A Rank • Lance Corporal`, and so on. They are cosmetic, non-mentionable, and created with no server permissions. Do not give them moderation or management rights; the bot refuses to use rank roles with server permission flags.
- The bot manages only the role IDs it created and recorded. It does not adopt or remove unrelated roles, even if they have similar names.
- On promotion/demotion it adds the new rank, removes old managed rank roles, then posts the announcement with the old/new rating and the batch's win/loss/kill/death changes. The member is displayed as a mention without sending a notification ping.
- Enrollment assigns Private without posting a promotion. If someone manually removes the correct rank role, the next successful cycle restores it.
- Keep the bot role above all rank roles. A permissions failure leaves saved rating changes pending and is retried. Check logs and `/rank` for the status.
- `/ranks-setup` is safe to rerun for recorded roles and recreates roles that were deleted. It preserves manually renamed roles by ID. Keep the SQLite database: losing it loses the managed-role ownership records, ratings, and baselines.

## Commands

### Daily linked-player standings

A new daily embed lists the **top 20 linked members currently in the server**, ordered by saved progression rating (highest first). It includes Discord mentions, rank names, and ratings, with medals for the leading places and shared positions for ties. Both administrator-linked and Steam-verified accounts qualify. Paused/held players remain listed with their status. No mention notifications are sent. It is cumulative progression, not a reset-every-day competition or a kills leaderboard.

By default it posts in the rank-announcement channel at **18:00 UTC** (19:00 during British Summer Time; 18:00 in the UK winter). Checks run every five minutes, so posting can be up to about five minutes later plus network delays. To change it, add Railway variables or `.env` entries:

```dotenv
RANK_DAILY_CHANNEL_ID=YOUR_DAILY_STANDINGS_CHANNEL_ID
RANK_DAILY_TIME_UTC=18:00
```

The channel variable is optional; blank uses `RANK_ANNOUNCEMENT_CHANNEL_ID`. The time is explicitly UTC and does not move with daylight saving. Give the bot View Channel, Send Messages, Embed Links and Read Message History in the destination. Restart/redeploy after editing these values.

One new message is posted per UTC date after the scheduled time, preserving the previous days' standings. Today's completed posting date is saved in SQLite so restarts do not normally duplicate it. If the bot starts after today's scheduled time, it posts today's standings on its next check; it does not backfill missed dates. No empty post is sent before anyone is linked. Changing channels after today's post takes effect for the next day's post.

The post uses saved ratings after the current scoring attempt. Source failures do not erase ratings; the post labels older active snapshots. A send failure retries on the next check. A send/save crash is recovered by looking for today's marker among the last 100 messages in the target channel; an unusually busy channel can exceed that window and allow a rare duplicate. Keep the persistent database and run one bot instance. A deleted daily post is not recreated after its date is recorded as completed.

| Command | Who | Purpose |
| --- | --- | --- |
| `/ranks-setup` | Manage Server | Create/repair managed cosmetic rank roles |
| `/rank-guide [channel]` | Manage Server | Post/repair the player guide and optionally choose its channel |
| `/link` | Anyone | Verify Steam and enroll without typing a Steam ID |
| `/rank [member]` | Anyone | Show rating, rank, next threshold, last scored source timestamp, and any hold/pending status privately |
| `/rank-pause member` | Manage Server | Stop scoring, remove managed rank roles, retain identity and rating |
| `/rank-resume member` | Manage Server | Resume a paused/held account with the same rating and a fresh baseline |

Pause/resume is the supported equivalent of unlink/relink. It does not erase progression or let members self-reset losses. Results gained while paused or during an unresolved counter-reset hold are skipped on resume. Already-active accounts cannot use resume to discard pending results. Incorrect identity registrations require a deliberate database correction by the server operator after a backup; there is no public reassignment/reset command.

## Reliability and limitations

- Rating, counters, rank, and pending announcements are saved together in SQLite before Discord changes are attempted. Repeated or older source snapshots do not earn points again. Half-points are stored as integers to avoid rounding drift.
- The bot retains baselines over downtime. On return, it scores the accumulated difference as one batch. Because the public feed has no event ordering and rating has a zero floor, this can differ from match-by-match scoring. It cannot determine opponents, individual match outcomes, or their order from these totals.
- Counter decreases pause that player's scoring without changing their rating. Very large changes also pause it: more than 60 total wins/losses or 10,000 kills/deaths per elapsed hour, with at least one hour of allowance. An administrator should review the source then use `/rank-resume`; this preserves rating and establishes a fresh baseline.
- Missing players, malformed feeds, and source data older than 15 minutes do not produce losses or reset ratings. Future source timestamps beyond five minutes are rejected. Error details go to the bot log. `/rank` shows individual counter holds. Progression is independent of player/clan display filtering.
- Members who leave Discord keep their saved identity and rating. Their active linked account can continue accruing game results. Role updates resume when they return; pause the account if you want scoring to stop. An undelivered rank transition waits for the member to return before subsequent scoring.
- Pending announcements retry after failures. A unique event marker searches the last 100 channel messages to recover a crash immediately after sending. In an unusually busy channel that exceeds the recovery window, a rare duplicate is possible. A dedicated announcement channel is recommended.
- The feed is a third-party public website feed, not a guaranteed service. It covers WDUK server stats rather than every WarDogs server. An upstream correction that increases counters cannot always be distinguished from real play.
- `/ranks-setup` saves each role ID immediately after creating it. A crash between creating a role and saving its ID can leave an unused cosmetic duplicate; remove that unused role manually after checking the saved setup.
- Keep one running bot process and persistent storage. Back up the database while the bot is stopped before deployments or manual data work. Turning the feature off by removing its channel variable stops processing but does not remove roles or erase ratings.

## Validation before launch

Automated tests cover the agreed formula, zero floor, thresholds/buffer, duplicate snapshots, stale/malformed data, source resets, identity uniqueness, persistence, role restrictions, and announcement retries/recovery, alongside existing squad and leaderboard tests. Discord calls are simulated in those tests.

After installing, verify `/ranks-setup`, register a confirmed member, check they receive Private and `/rank` reports zero, then confirm the next published new game results change their rating. Verify promotion/demotion delivery in a test server before enrolling the whole community. No changes were made to your live Discord during development.


