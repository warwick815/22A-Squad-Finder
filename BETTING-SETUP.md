# 22A virtual betting update

## Install
Upload the Python files from this package to your existing GitHub bot repository, preserving the rank_badges directory. Let Railway deploy. Keep your Railway variables and persistent /data volume unchanged. Never upload a database or .env file. This package contains neither.

Create a text channel such as #betting. Give the bot View Channel, Send Messages, Embed Links and Read Message History there. Staff with Manage Server run `/betting-panel channel:#betting`. The panel is persistent across restarts. Repeating the command in the same channel updates its saved panel.

## User flow
Members must /link Steam first. Each receives $10,000 virtual dollars once, saved in the existing SQLite database. No top-ups, purchases, transfers, cash-outs or ELO effects.

Create Bet → choose opponent → fill the terms modal:
- `kills`: challenger bets the opponent will FAIL to reach the target. The opponent wins by reaching or exceeding it.
- `race`: more additional kills wins; target/death-limit inputs are ignored. Ties refund both stakes.
- `limit`: opponent must reach the kills target without exceeding the specified number of additional deaths.

Stake is $100–$1,000 per person. Duration is a whole number of hours from 1 to 6. One offered or active bet per person. Challenger's stake is reserved on creation. Offers appear in the betting channel on the next minute check; they do not ping members. The opponent opens My Bets to accept or decline. Acceptance reserves their matching stake. The creator may cancel an unaccepted offer. Offers expire after ten minutes and return the reserved stake. Active bets cannot be cancelled by players.

Example: KingOlly offers Warwick a kills challenge, target 20, 1 hour, stake $500. Warwick accepts. At least 20 additional kills means Warwick receives the $1,000 pot, a net $500 gain. Fewer means KingOlly receives it.

My Wallet shows available and reserved funds. Leaderboard ranks wallet plus reserved funds. My Bets shows the open bet, or up to three recent results. Public challenge messages are edited when accepted or settled, normally on the next minute check. No duplicate payout when the bot restarts or a button is clicked twice.

## Measurement and refunds
These are approximate, cumulative-snapshot challenges, NOT exact one-hour match records. Starting data must be 0–5 minutes old at acceptance. Each required player's first observed source snapshot at or within five minutes after the nominal deadline is used. Actual measurement timestamps appear in results. Snapshot intervals can differ between players/sources. Do not use this game for real stakes.

Observed counter decreases or source/account changes refund both stakes. Future timestamps are not used. If suitable ending snapshots are unavailable fifteen minutes after the deadline, both stakes are refunded. Restarting preserves active bets and deadlines; an extended outage may result in refunds. The bot cannot detect resets that happen and recover entirely between snapshots. It trusts the provider's counters and cannot prove that kills were legitimate or identify farming.

Staff can use `/bet-refund bet_id:... reason:...` for an unresolved bet. The ID is in the public challenge footer. Refund reasons and staff IDs remain in stored history. Settled bets cannot be refunded again.

## Private response cleanup
Betting replies and player profile/comparison views automatically delete after three minutes while the bot stays running. Public panels, shared profiles, challenge records, announcements and leaderboards remain. Other existing menus, including Steam sign-in and staff controls, retain their current behaviour. Existing private messages cannot be cleaned retroactively. If Railway restarts during the countdown, users may still need to dismiss that reply. Discord interaction tokens expire, so cleanup is best-effort and cannot be recovered indefinitely after a restart.

## Scope
This release includes kills, head-to-head kills and kills-with-death-limit challenges. Wins, cash and WARDOGS Tools level bets are not enabled. All existing squad, rank, profile, insignia, nickname and roast features are retained in the bundled source. Test suite: 136 passing at packaging time; live Discord/Railway testing still requires deployment.
