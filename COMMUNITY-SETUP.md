# 22A Community Update

Upload all eight Python files from this ZIP together to the bot repository, replacing existing versions. community.py is new. Keep existing variables and the existing persistent /data volume; do not replace or delete the database. No new dependencies. Deploy one instance.

## Live ELO standings
Uses LEADERBOARD_CHANNEL_ID by default, as a separate embed from the game/clan leaderboards. Optional ELO_LEADERBOARD_CHANNEL_ID overrides the destination. The bot edits the same message every five minutes and remembers its ID across restarts. Top 20 linked current server members, including saved paused/held ratings. Empty standings are allowed. Ratings are community points, not opponent-adjusted Elo. Existing daily standings continue.

## Rating history
Use the player hub's Rating History button, or /rating-history. Use page:2 for older entries. Admins with Manage Server can use member: to inspect another player. History begins with this update, preserves existing ratings, and survives restarts in the same database. Feed snapshots can contain multiple games; this is not per-match history. Entries include original scoring weights and applied points (including the zero floor). Unchanged snapshots do not add entries. History is retained without automatic deletion; monitor database size over time.

## Weekly report
Defaults to the rank-announcements channel. Optional WEEKLY_REPORT_CHANNEL_ID selects another channel. Posts Mondays at 18:00 UTC (19:00 UK summer time), covering the previous Monday–Sunday UTC. If offline, catches up the latest completed week on the next check after its scheduled time; older missed weeks are not backfilled. The first partial week is labelled. No report is posted for weeks before history recording began.
Reports aggregate recorded result changes for linked current members: player-wins/losses (not distinct team matches), kills/deaths, top positive rating gains, promotion/demotion event counts. Admin corrections are excluded from gains and counted separately. Delayed source results count when processed, not their unknown match date. Missing data cannot be reconstructed; these are recorded totals, not guaranteed complete match statistics.

## Admin panel
Run /admin-panel channel:#your-staff-channel. Persistent buttons survive restarts. Each click AND modal submission checks Manage Server permission and server context. Status shows linked/paused/held accounts, pending announcements and last successful cached feed timestamp. Pause/resume and rating corrections ask for a Discord member ID and an audit reason. Enable Discord Developer Mode to copy member IDs. Corrections accept whole points from -10000 to +10000, floor rating at zero, update rank roles and announce rank changes. Resume preserves rating and establishes a fresh baseline, excluding paused results. History is private to the member or admins. Existing /rank-pause and /rank-resume still work; use the panel when an audit reason is needed.

## Permissions and verification
Destination channels need View Channel, Send Messages, Embed Links and Read Message History. Keep Manage Roles and rank hierarchy unchanged. After deploy: verify /rating-history, the hub button, one live standings message, and /admin-panel in a staff channel. After another deployment verify the same rating, history and live message ID. Test a correction on a designated test account and reverse it with a documented correction if desired. Automated tests run offline; live Discord/Railway deployment is not performed by this package.
