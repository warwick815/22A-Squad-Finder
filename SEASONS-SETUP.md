# Seasons and future level gains

Upload all six Python files from this update together. Keep the existing database and persistent volume. Installing does NOT reset ratings. Season numbering starts at 1 for the existing community rating period; no game-season detection is attempted.

## Enable bonuses

After checking a member owns their connected public WARDOGS Tools profile, run `/approve-tools member:`. Public URLs do not prove ownership, so approval is an admin responsibility. One profile cannot be approved for multiple members. Relinking a different profile stops bonuses until reviewed; it does not award old progress.

Each NEW Wardog level earns +2 rating and each NEW role level earns +1. Starting levels award zero. The first fresh eligible snapshot establishes the baseline; this may occur later than approval if the feed is stale or the player paused. Checks run in the progression loop, with the Tools 15-minute fetch cache. No need to open a profile. Snapshots older than 30 minutes or more than five minutes in the future are ignored. Corrections use per-level high-water marks to avoid rewarding the same climb twice. Level bonuses are recorded in rating history and can promote players. Cash remains display-only. Combat scoring and rank thresholds stay unchanged.

## End a season

At the game season boundary, an admin runs `/season-end` and presses the confirmation button. This is intentionally admin-triggered: there is no verified automatic season-change signal. Do NOT use it now unless you want to close the current season. Review rank thresholds before starting the next season as planned.

The bot archives full player records in the database and resets current ratings to 0 / Private, preserving Steam links, preference roles, approval mappings, history and manual pauses. Fresh post-reset combat and level snapshots establish baselines without historical rewards. The uncertain gap before those baselines is excluded.

On the next check, a permanent final top-20 Season ELO Standings message is posted to ELO_LEADERBOARD_CHANNEL_ID, otherwise LEADERBOARD_CHANNEL_ID, otherwise the daily standings channel. Full records remain archived even for members outside the top 20. Failed posts retry with a saved message key. The existing live ELO board becomes the current season board. Daily posts continue. Do not delete the database or volume.

This version does not automatically discover the game's season date, recalculate old levels, or change rank thresholds. It has been tested offline; deploy and verify command availability in your server.
