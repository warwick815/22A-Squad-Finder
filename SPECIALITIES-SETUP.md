# 22A speciality roster

Replace bot.py and preferences.py and add specialities.py alongside them. Keep all your other bot modules, Railway variables and persistent database. This update does not reset any existing data.

Give the bot Manage Roles and put its role above the new speciality roles and members it needs to manage. In #roles grant View Channel, Send Messages, Embed Links and Read Message History. Keep Server Members Intent enabled as required by the existing bot.

Run `/roles-panel channel:#roles` with Manage Server permission. This creates/reuses 16 cosmetic roles, posts four category rosters, then posts the selection panel. Run it again in the same channel to repair missing roles or refresh the panel. Repeated setup reuses saved role IDs and exact matching role names. It does not delete any pre-existing preference panels; remove obsolete posts manually if wanted.

Members press Choose Specialities. Every option includes its category. Choose one primary, then up to three secondaries. The primary cannot also be a secondary. Choices save immediately; My Selections reviews them and Clear Selections removes them. No Steam link is needed to select specialities. Linked player profiles and shared profiles include the choices.

Existing team preferences and the six general play roles are preserved. We do not guess a detailed speciality from a general preference; members make their own choices.

The roster refreshes once per minute and lists actual assigned speciality roles with member counts. A star denotes the saved primary. Members may appear in multiple lists. Empty roles show No volunteers yet. Large lists split into additional fields/pages. Roster updates do not ping members. Normal edits reuse the same posts; additional overflow pages may appear after the selection panel when the community grows.

Role assignment failures keep the desired choice as pending and retry each minute. The member sees an explanatory message. ELO rank roles, team roles and other access roles are never removed by this feature. Speciality roles must remain cosmetic: do not attach permissions or channel access overrides. Staff-assigned speciality roles also appear in the roster; they have no primary star unless selected through the panel.

Selections, role IDs and destination channel survive restarts. The setup command intentionally requires reusing the configured channel rather than leaving multiple live rosters behind. Weekly/daily reports and rating calculations are unaffected. Live Discord verification is required after deployment; 149 offline tests passed at packaging time.
