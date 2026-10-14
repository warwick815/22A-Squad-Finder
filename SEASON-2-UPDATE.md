# Season 2: divisions and cash rewards

Deploy before staff use End Season. Installation does not reset ratings, wallets or linked accounts. The existing staff-confirmed season reset archives records and starts players at zero. Season 2 and later use the new thresholds; Season 1 retains its thresholds. New enrollees receive the active season rules on the next scoring poll.

## Promotion thresholds
Private 0; Lance Corporal 313; Corporal 938; Sergeant 1,875; Staff Sergeant 3,750; WO2 6,250; WO1 10,000. These are 25% above the old thresholds, rounded up. The existing 50-point military demotion buffer remains. Each rank range has Bronze, Silver and Gold divisions; boundaries round up. WO1 Silver starts at 11,250 and Gold at 12,500. Divisions follow rating directly, with no separate demotion buffer. Military roles and nickname abbreviations remain unchanged.

## Cash rewards
Season 2 awards +1 rating for each $10,000 newly earned WDUK cumulative cash, capped at 25 cash points per UTC source date. The first fresh observation after reset establishes a baseline; old money never earns points. Partial amounts carry forward. Whole points above the daily cap are discarded, not banked. Delayed earnings are attributed to the date observed, since the API has no per-match cash events.

Spending, betting wallets, share proceeds and Tools cash do not affect this reward. Missing/invalid/stale cash data awards nothing. Corrected lower totals cannot be rewarded again when they recover. Source changes rebaseline. Paused or held accounts do not earn cash points. Existing combat and approved level rewards remain unchanged.

## Displays
Discord profiles now have division colours and a three-step milestone display. Website profiles show a matching coloured division banner and progress; standings include the division beside military rank. /rank uses the appropriate threshold. Refresh /rank-guide and /player-panel after deploying; reopen profiles to see changes. The guide explains both Season 1 and Season 2 rules.

No new variables or database migration commands are needed. Keep Railway /data and existing environment variables. This complete package includes the earlier Black Market, wallet and radar updates. It has not been deployed; browser visual verification was unavailable.
