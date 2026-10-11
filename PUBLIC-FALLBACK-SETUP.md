# Progression public-feed fallback

Upload progression.py and progression_sources.py alongside your existing bot.py, then let Railway deploy. Keep your WDUK_API_KEY, DATABASE_PATH and persistent volume unchanged. No Discord setup command or relinking is required.

Every progression check uses fresh clan API data first. Linked Steam IDs missing from that feed are looked up in the public all-time leaderboard JSON feed. If the API fails validation, is stale, or is unavailable, the public feed is checked independently.

Once a linked player has a valid public row, their public-source choice is saved in SQLite. API recovery or clan-tag changes do not move them back. Existing public-source players and Warwick's prior override are retained. Missing/stale public data pauses updates for public-source players; it does not switch them back to the API.

Matching is exclusively by linked SteamID64. Display names and clan tags are not used for identity. A player absent from both feeds must wait until their verified ID is present. Freshness and counter validation remain enabled.

New members start at zero with a baseline and receive no historical awards. Existing players keep their rating and links. Moving from API to public data starts a fresh baseline, so the transition interval may not earn points. Active betting challenges detect source changes and refund rather than comparing mixed-source counters.

This updates progression, player profiles and the progression feed used by bets. It does not change the separate public clan leaderboard or WARDOGS Tools level feed. Profile timestamps use the oldest included fresh source timestamp conservatively.

After deploying, allow one successful five-minute check, then reopen the player's profile. If the player remains missing, verify the linked Steam ID, not the displayed name. Both feeds must still be reachable from Railway. Offline tests cover routing, outage fallback, source persistence, migration and stale-data rejection; no live provider data or credentials were used for these tests.
