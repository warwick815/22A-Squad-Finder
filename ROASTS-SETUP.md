# Barracks banter

Upload bot.py, roasts.py and corporal.png together to the existing repository. Keep the picture beside bot.py. No extra dependencies or AI key needed.

Before enabling: in Discord Developer Portal, select your application, open Bot, and enable Presence Intent under Privileged Gateway Intents. Keep Server Members Intent enabled. In Railway set ROASTS_ENABLED=true and deploy. Optional ROAST_CHANNEL_ID can identify the exact wardogs-chat channel; otherwise the bot requires exactly one text channel named wardogs-chat. Bot needs View Channel, Send Messages, Embed Links and Attach Files there.

Every randomly chosen 1–3 hours, the bot selects an online/idle/DND human currently in a voice or stage channel and able to view the destination. Invisible/offline users and bots are excluded. Each member has a 24-hour cooldown. If no one is eligible, it skips that slot and schedules another 1–3 hours later. It never queues missed posts. Schedule, cooldowns and pause state survive restarts on the existing volume. Run only one bot instance.

The message mentions only the selected member, uses the supplied image and one of 100 original profane military-banter lines. An unofficial fictional-parody footer avoids implying endorsement. There is no opt-out button. Staff with Manage Server can use /roasts paused:true or /roasts paused:false; resuming schedules a fresh 1–3-hour wait. To disable presence intent requests, set ROASTS_ENABLED=false and redeploy.

For manual roasts, upload community.py and roasts.py and redeploy, then run /admin-panel in your staff channel to refresh the dashboard. Choose Roast a Member and select a Discord member. This posts immediately, including when scheduled roasts are paused. Manual roasts require Manage Server and bypass the online/voice requirement and automatic member cooldown. There is a server-wide 60-second manual cooldown. The existing corporal.png image and ROASTS_ENABLED=true setting are required.

Enabling Presence Intent in code without enabling it in the portal can prevent the bot from connecting. Install the files and enable the portal setting before enabling ROASTS_ENABLED. This feature changes no ranks, ratings or profile links.
