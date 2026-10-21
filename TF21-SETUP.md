# TF21 community servers

Play on TF21's community servers counts towards ELO and profile stats alongside WarDogs UK.

## Setup

Railway → bot service → Variables → `tf21_api_key` (or `TF21_API_KEY`) = the token TF21 gave you → redeploy.
The token is sent only to `https://tf21.net/api/v1/22a-players` as `Authorization: Bearer …`.

After redeploying, the log shows within five minutes:

`TF21 feed connected: N player row(s) usable of M; fields …`

If N is 0 while M is not, send the field list from that line so the reader can be matched to it.

## How it scores

- Players are matched by Steam ID, so only members linked through the Player Hub are scored.
- Each player's first TF21 reading is a baseline: earlier TF21 play never earns points.
- New TF21 kills, deaths, wins and losses then use the same weights as WarDogs UK
  (win +20, loss −10, kill +5, death −3), recorded in rating history as "TF21".
- TF21 has its own baseline. If its totals go down or jump impossibly, only the TF21 side
  restarts from the new totals without points; WarDogs UK scoring is never paused by TF21.
- A new season clears the TF21 baseline like everything else.

## What shows where

- Profiles, the public page and ribbons use combined kills, deaths, wins, losses, team kills and K/D.
  Hours played, cash and kills per hour stay WarDogs UK only (TF21 does not report time played).
- Profiles show a "TF21 servers" line with that player's TF21 totals and whether they are on a TF21 server now.
- Fantasy Squad scoring, Operations and season stat boards still use WarDogs UK only.
