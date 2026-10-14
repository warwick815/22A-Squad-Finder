# Performance market update

Player shares now use newly observed rolling 24-hour performance: kills +2, deaths -3, team kills -20. The target is $100 plus that score, plus $1 per 100 ELO (maximum $20). Prices move gradually, with a 15% maximum movement in either direction over 24 hours and a $25 minimum.

Inactivity has a **one-day (24-hour) grace period**, followed by 2% daily compounded decay, capped at 20% of the price when decay began. Increasing playtime or game counters counts as activity. Returning to play stops decay; it does not instantly restore the old price.

Only continuous, fresh observations count. Missing/stale data, changed sources, counter resets and season changes require a new baseline; gaps never receive backdated penalties. Trading pauses until fresh valid observations and an active rating are available. Kills, deaths, team kills, hours played, wins and losses must all be present. These are snapshot differences, not precise match events.

Existing share quantities, purchase costs, wallets and ELO are preserved. Initial prices start at the previous ELO-based price; historical stats do not retrospectively reprice holdings. Existing season settlements, selling fees and staff reset behaviour remain in place.

## Install on Railway

Replace the application files using this complete package, then redeploy your existing service. Keep Railway variables and the existing /data volume. No new environment variables are required. Do not reset betting or remove the database.

Allow two fresh source observations for initial market availability. Website assets include a new cache version. Discord Web View buttons are included; refresh existing panels using /rank-guide, /player-panel and /betting-panel if needed.

This document supersedes earlier documentation describing share prices as purely ELO-based. The package does not deploy itself.
