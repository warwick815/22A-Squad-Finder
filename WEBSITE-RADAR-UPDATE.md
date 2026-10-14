# Standings, wallets and radar design

Standings show every available combat stat, ELO and spendable Black Market wallet balance. Rank by now places the selected metric first and highlights it. All measures sort highest first, with tied positions shared. High deaths, losses or team kills do not imply better performance. Missing values remain unavailable rather than zero. Scroll horizontally for all columns; player names stay visible.

Profiles show available virtual dollars, reserved bets and shares at purchase cost separately. Unaccepted incoming offers are not reserved. Held shares are not counted as spendable cash, and their purchase cost is not a live valuation. Wallet summaries are visible to signed-in server members through the existing standings/profile access rules. No new public endpoints or wallet changes are introduced.

The home grid now has a decorative radar sweep and simulated contacts. This is not live player tracking. A pause button and reduced-motion support are included. Panels, stat cards and standings have updated styling.

Install the full package into the existing Railway project and redeploy. Keep the /data volume and existing variables. Refresh your browser after deployment. No database reset is needed. Not deployed by this package.

Browser visual verification was unavailable; automated server tests and JavaScript syntax/sorting checks were run.
