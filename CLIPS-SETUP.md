# Clips page setup

Medal links posted in the 🎬clips🎬 channel appear on the website's **Community → Clips** page (members only).

Do these in this order. If step 2 happens before step 1, Discord refuses the bot's connection and it goes offline.

1. **Discord Developer Portal** → your bot's application → **Bot** → **Privileged Gateway Intents** → switch on **Message Content Intent** → Save.
2. **Railway** → the bot service → **Variables** → add `CLIPS_CHANNEL_ID` = `1561738686327029781` → redeploy.
3. In Discord, make sure the bot's role can **View Channel** and **Read Message History** in 🎬clips🎬.

On start-up the bot reads the last 300 messages in the channel, so existing clips appear straight away.

## How it behaves

- Any medal.tv link in the channel becomes a clip; the title and thumbnail come from Discord's link preview.
- 🔥 and 👍 reactions on the post count towards **Top clips**.
- Deleting the Discord message (or editing the link out) removes the clip.
- Staff (Manage Server) can hide a clip from the website without touching Discord.
- Clips play in the page using Medal's player; **Open on Medal** always works if a clip won't play inline.
- To switch the feature off, remove `CLIPS_CHANNEL_ID` and redeploy. You can then turn the intent off again.
