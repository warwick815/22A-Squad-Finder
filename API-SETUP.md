# WDUK authenticated API update

1. Upload all NINE Python files from this ZIP together to GitHub. wduk_api.py is new; community.py must remain included.
2. In Railway set WDUK_API_KEY to the provided key. Keep the value private; never add it to GitHub. The endpoint and header are configured in code; no URL variable is needed.
3. Keep LEADERBOARD_PERIOD=all for API-backed player standings. Weekly/daily game boards and the top-clans board still use the public feeds; no authenticated endpoints for these were provided.
4. Keep your existing /data volume and DATABASE_PATH. Do not replace the database. Redeploy one bot instance.

The verified endpoint is https://hq.wardogs.uk/api/clans/22A/players. It returns player Steam IDs, lifetime counters, profile metrics and updatedAt. The bot reads the key from the environment and sends it only to this HTTPS endpoint; redirects are disabled. API errors never trigger an automatic switch to public scoring data. Saved stats remain visible while retries run every five minutes. A shared cache prevents the progression and player leaderboard tasks from fetching separately within a five-minute window. Provider rate limits have not been supplied.

With the key present, progression, cached player profiles and the all-time player game leaderboard use the clan API. ELO standings, rating history and weekly reports use the saved progression results. Only players included in the clan endpoint can receive new stats; absent players retain ratings. The clan membership list replaces name substring filtering on the API-backed board.

On the first fresh API snapshot for each player, their current rating, history, rank, Steam verification and pause/review state are preserved. Only the scoring baseline switches; no points are awarded for the gap between the last public snapshot and the first API snapshot. Later snapshots score normally. Removing the key also causes a one-time baseline reset back to the public source. Source timestamps must be timezone-aware, no more than 15 minutes old or 5 minutes in the future; bad data leaves ratings unchanged.

Confirm the player leaderboard footer says WDUK clan API, the player profile receives fresh stats, and existing ratings/Steam links remain. Live API schema was checked successfully during development. Discord/Railway deployment has not been performed by this package.

## API diagnostic hotfix
Older valid API snapshots can now display with a stale-source warning. Progression still refuses snapshots over 15 minutes old; it does not award points from stale data. API failures report safe categories (HTTP status, network, TLS, timeout or invalid schema) without printing credentials or response bodies. This does not clear existing player review holds. Use /rank to inspect those separately.
