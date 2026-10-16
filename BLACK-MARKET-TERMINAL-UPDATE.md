# Black Market trading terminal and daily ELO rewards

## Website
- Trading-terminal layout with responsive panels, sortable market prices, recent-price sparklines and a clearer order ticket.
- Your stock: own share price, shares held by other members, remaining supply and number of holders. Open your own price-history chart. No self-trading.
- Today's net realised profit and projected daily ELO reward displayed separately from unrealised portfolio value.

## Reward rules
- Starts with newly settled profit after installing this update; no historical payouts.
- Each UTC calendar day is a 24-hour period. Settlement runs after midnight UTC on the progression poll, normally within five minutes.
- Net profit is share-sale proceeds after the 2% fee minus allocated purchase cost, plus challenge profit minus challenge losses.
- Every complete $1,000 of positive daily net profit awards 20 ELO. Example: $2,500 net profit awards 40 ELO.
- No ELO deduction for a negative day. Daily fractions do not carry forward. No reward cap.
- Starting wallets, deposits, stake returns, refunds, season share refunds and unsold gains do not count.
- Active linked progression with an established baseline is required. Paused/reviewed rewards wait until eligible in the same season. Previous-season unpaid rewards expire rather than entering the next season.
- Reward receipts are saved with ratings to prevent duplicate credit across retries and restarts. Bonuses appear in rating history and use normal rank transitions.
- Staff betting resets preserve the profit ledger and reward receipts; they do not re-award bonuses.

## Deployment
Upload this complete package to the existing Railway service and redeploy. Keep environment variables and the /data volume. No reset, new secret or migration command is needed. Existing Discord Black Market messages may need to be reposted with the panel command to show the revised description. The rank guide updates through its normal refresh.

## Validation
229-test regression suite passed; the expanded exchange API tests (12) also passed, including own-stock totals and blocked self-trading. JavaScript syntax and UI rendering checks passed. Full browser visual inspection was not completed. This package has not been deployed.
