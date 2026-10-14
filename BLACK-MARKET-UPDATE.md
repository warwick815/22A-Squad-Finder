# The Black Market update

The website and Discord betting panel are now named The Black Market. Existing commands, URL fragments, channel settings and wallets are unchanged, so old links continue to work. This package does not rename the Discord channel itself.

## Limited stock
Each player has 500 shares available across the whole community, with a maximum holding of 100 per member. Buying reduces availability; selling returns shares to the pool. Supply is checked both when a quote is requested and when the trade commits under the existing betting lock. Sold-out players can still be sold. Buying and selling do not themselves change the performance-based price.

Existing holdings are never confiscated. If an existing player has more than 500 shares held, no more can be bought until total holdings fall below 500. Season settlements and staff betting resets release the pool through their existing settlement/reset behaviour.

## Price history
Click a player's name in the share-price table to open their graph. Choose 24 hours, 7 days or 30 days. Green segments show increases or unchanged prices; red shows decreases. Hover over a recorded point for its time and price, or expand the accessible recorded-prices table. Gaps exceeding two hours are not joined.

History is persisted in the existing database as hourly observations for up to 30 days. It starts collecting after installation: past prices are not fabricated. A new player needs two hourly observations for a graph. Observations retain the latest price within each UTC hour. Existing 24-hour inactivity grace and performance pricing are unchanged.

## Install
Upload this complete package to the existing bot project and redeploy Railway. Keep the /data volume and all existing variables. No new secrets or database reset are needed. Run /betting-panel in Discord to update the existing embed title. Refresh the website to load the new assets.

Automated checks are included in tests/. Browser visual verification was unavailable in this session. This package has not been deployed.
