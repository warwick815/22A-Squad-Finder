# Season-scoped standings fix

The standings season selector loads a complete separate board: ELO, kills, deaths, K/D, wins, losses, hours, cash earned, kills/hour, team kills, suicides and win rate. Ratios are calculated from season counters, never lifetime ratios. Every archived participant is included, not just the top ten. Current wallet balances are separately labelled and not presented as seasonal earnings; historical wallet balances and weekly movement are unavailable.

Season statistics are persisted inside each progression player record. Closing a season deep-copies them into the immutable season archive, then initialises all new-season counters at zero. The first fresh post-boundary source observation establishes the baseline; subsequent observed increases count. Duplicate or out-of-order observations do not count twice, source changes establish a new baseline, and corrected lower totals do not re-award the same recovered totals. Season combat statistics count observed play independently of ELO scoring pauses.

Lifetime source rows, player-profile statistics and all historical season ELO records are unchanged. Selecting a season only changes the displayed board. Player-profile links still open current lifetime profiles.

## Existing data limitation
Earlier versions did not archive complete season combat counters. Such historical fields show a dash with "Season statistics not recorded" rather than misleading lifetime totals. Existing active players begin prospective tracking at installation, labelled partial: this update cannot reconstruct missing hours/cash/team kills or other unrecorded historical data. It never treats current lifetime totals as season totals. Full tracking applies to new seasons after the first fresh baseline. Cached data cannot be counted across the reset boundary.

## Installation
Deploy this complete package to the existing Railway service. Keep /data and all variables. Do not reset the season to install this fix. Refresh the browser for the new Season selector. Future staff season closures automatically archive the complete recorded board. No live deployment or reset was performed while preparing the package. Visual browser verification was unavailable.
