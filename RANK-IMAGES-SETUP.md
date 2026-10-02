# 22A rank artwork update

1. Upload progression.py, player_panel.py, rank_images.py and rank_nicknames.py to the repository beside bot.py.
2. Upload the complete rank_badges folder, keeping all seven PNG files inside it.
3. Let Railway deploy. Your database, linked accounts and ratings are unchanged.
4. Give the bot Create Expressions permission in Discord, and ensure seven free emoji slots are available. Staff running setup need Manage Server.
5. Run /rank-images-setup once in your server. It reuses existing rank22a_* emojis if run again.
6. Reopen a player profile. The current-rank image replaces the avatar thumbnail, with inline current and next-rank badges. Future promotion/demotion announcements use the rank image too. Existing announcement history is unchanged.

If a badge is unavailable, the existing standard emoji remains as a fallback. Keep these server emojis unrestricted so the bot can use them.

The PNGs are 128 by 128 transparent-background exports of the approved artwork. Names: pte, lcpl, cpl, sgt, ssgt, wo2, wo1. PTE uses a blank cloth slide because Private has no rank insignia. Nickname abbreviations remain unchanged.
