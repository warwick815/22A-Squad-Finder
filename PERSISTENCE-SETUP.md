# Keep Steam links and ratings across updates

**Preserve the existing database before deploying this update or changing Railway storage.** Uploading to GitHub may automatically redeploy, so do not upload yet if your current data is on temporary storage. A code update cannot recover a database that an earlier deployment already discarded.

## What is fixed

- `/link` and the Link Steam button immediately recognize a saved Steam-verified account and respond “already linked”. They do not start a new Steam login or reset its rating.
- Completed links, Steam verification, ratings, baselines, role IDs and message IDs remain in the existing SQLite database. The memory-only 10-minute login sessions are still temporary; only an unfinished login needs restarting after a deployment.
- On Railway, startup now requires an attached persistent Volume and a DATABASE_PATH inside it. It refuses to run using temporary container storage.
- A storage identity marker records the database path and identity. Subsequent startup refuses an unexpectedly missing/replaced database or a changed path rather than silently creating a blank replacement. Keep the marker with the data. A completely replaced/deleted volume also loses its marker, so this is not protection against deleting the volume itself.
- A consistent SQLite backup is created at startup and once per UTC day while progression runs. The latest seven daily backups are retained in a `backups` directory beside the database. These backups share the volume; they do not survive deletion of the entire volume. Keep an off-volume backup or Railway volume backups too. Recovery is manual, not an automatic rating rollback.
- Logs show the resolved database path and database identity, without tokens.

## Check the current setup first

In Railway, note the bot service's **DATABASE_PATH**, whether it has a **Volume**, and that volume's **mount path**. No token is needed for this check.

Examples of valid pairs:

| Volume mount | DATABASE_PATH |
| --- | --- |
| `/data` | `/data/22a.sqlite3` |
| `/app/data` | `/app/data/22a.sqlite3` |

Keep the existing path and database if already persistent. Merely typing `/data/22a.sqlite3` does not create or attach a volume. Switching to a new empty file will make old accounts appear absent; migrate the existing database before switching. The volume must be attached to the bot's actual service/environment. Railway supplies `RAILWAY_VOLUME_MOUNT_PATH` automatically; do not manually fake this variable to bypass the check.

## If the current database is outside a volume

The current running container may be the only remaining copy. Before redeploying, use a shell in that deployment (for example Railway SSH) to make an SQLite-consistent export. This example is for the `/app` layout shown in this bot's Railway logs and respects DATABASE_PATH if set:

```sh
python -c "import os,sqlite3; from pathlib import Path; p=Path(os.environ.get('DATABASE_PATH','/app/data/22a.sqlite3')); p=p if p.is_absolute() else Path('/app')/p; assert p.is_file(), 'Database not found; stop and check DATABASE_PATH'; s=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True); d=sqlite3.connect('/tmp/22a-before-update.sqlite3'); s.backup(d); assert d.execute('PRAGMA quick_check').fetchone()[0]=='ok'; d.close(); s.close(); print('Backup ready: /tmp/22a-before-update.sqlite3')"
```

Download that backup **before stopping/redeploying**. With a current Railway CLI linked to the correct project/service:

```sh
railway service files download /tmp/22a-before-update.sqlite3 ./22a-before-update.sqlite3
```

Keep it private: it contains member IDs and progression data. Do not commit it to GitHub. This captures a consistent point in time; scores earned afterwards are not included in the backup, so minimize activity/delay before migration.

Then attach persistent storage and arrange to restore the exported SQLite file to the intended DATABASE_PATH **while the bot is not writing to it**, before normal bot startup. Use a maintenance deployment/file-transfer approach appropriate to the service. Do not overwrite a live SQLite database or leave a different database's WAL/SHM files beside the restored copy. Get assistance with the exact migration sequence after confirming your current settings; do not just change paths and let the bot register everyone again.

Current Railway supports service file browsing/downloading/uploading: [CLI file operations](https://docs.railway.com/cli/service). Storage reference: [Railway volumes](https://docs.railway.com/volumes).

## Install after data is preserved

1. Verify the populated database is inside the attached volume. Keep its existing server/channel configuration.
2. Extract `22a-persistence-update.zip` and upload all **seven Python files** to GitHub: bot.py, config.py, state.py, leaderboard.py, progression.py, steam_link.py, player_panel.py.
3. Deploy one instance. The first protected startup creates the identity marker alongside/on the database storage and logs its identity. Existing records are reused.
4. For a previously Steam-verified member, press Link Steam: it should say **already linked**. Check My Profile and `/rank` show the previous rating, not zero.
5. Note the database identity in the log. Redeploy once more, confirm it is unchanged, and confirm the same member's profile still works without signing in.

If startup reports missing volume, changed path or identity mismatch, do not delete the marker or database to force a clean start. Correct the mount/path or restore a verified backup. If links/ratings were already erased and no backup exists, code cannot reconstruct verified ownership and historical ratings from the public leaderboard.

The patch passed 83 offline tests, including database reopen/backup preservation, missing-database refusal, volume-path checks and already-linked behaviour. Your actual Railway volume and data still need checking; they were not accessed or changed during development.
