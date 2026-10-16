# Player Exchange dashboard redesign

The exchange now uses a three-column trading dashboard inspired by the supplied reference:
- Left: compact searchable/sortable market watch with prices and miniature trends.
- Centre: personal stock and daily reward cards, followed by a large selected-player chart with 24H/7D/30D controls and exact recorded prices.
- Right: existing reviewed order ticket and a compact portfolio with position values and allocation bars.
- Player selection updates the inline chart and order ticket. Viewing your own stock leaves the order ticket on another player; self-trading remains blocked.
- Charcoal surfaces, restrained green/red price indicators, consistent spacing and responsive layouts.

Charts use recorded hourly prices. Missing observations remain gaps; no invented candles, volume, portfolio history or market news. Empty histories explain when observations are needed.

Trading, wallet and ELO reward calculations are unchanged from the included Black Market reward update. This is a complete application package. Preserve Railway variables and /data; no reset is required.

Validation: JavaScript syntax and targeted chart/portfolio checks passed (empty/flat series, gaps, duplicate observations, range filtering and escaped player names). Full browser visual inspection has not been completed. Not deployed.
