# infra/backup-dr

Backup schedules, restore runbooks, disaster-recovery plans.

## Nightly database backup

The API host (the Docker LXC running `infra/docker/docker-compose.api.yml`) backs up its Postgres
database every night at about 02:30 with a systemd timer.

| File | Installed as | Does |
|---|---|---|
| `eos-db-backup.sh` | `/usr/local/bin/eos-db-backup` | `pg_dump` (compressed custom format), checks the archive is readable, writes a `.sha256`, prunes old copies, copies to the second location |
| `eos-db-restore.sh` | `/usr/local/bin/eos-db-restore` | `--check`: restore into a throwaway database and count rows. Without it: replace the live database |
| `eos-db-backup.service`, `.timer` | `/etc/systemd/system/` | run the backup nightly; a run missed while the host was off happens at boot |
| `eos-db-backup.env.example` | `/etc/eos/db-backup.env` | settings: folders, how many to keep, second location |
| `install.sh` | | one-time install |

Backups land in `/var/backups/eos/daily/eos-<UTC time>.dump`; each Sunday's is also kept in `weekly/`.
Defaults keep 14 nightly and 8 weekly copies. `/var/backups/eos/last-success` holds the time, size and
name of the last good backup.

### Install (once, after the API is deployed)

```
bash /opt/education-os/infra/backup-dr/install.sh
```

It installs the scripts and timer, writes `/etc/eos/db-backup.env` if missing, and takes the first
backup straight away. Set the second location in that file (below).

### Check it is working

```
cat /var/backups/eos/last-success          # when the last good backup ran
systemctl list-timers eos-db-backup.timer  # when the next one runs
journalctl -t eos-db-backup --since -2d    # what the last runs said ("ok: ..." or "FAILED: ...")
ls -lh /var/backups/eos/daily/
```

`last-success` older than a day means the backup is failing: read the journal.

### Test a restore (monthly, and after any change to the database setup)

```
eos-db-restore --check /var/backups/eos/daily/<newest>.dump
```

Restores into a throwaway database `eos_restore_check`, prints the rows in every table, then drops it.
Live data is not touched. A backup is only proven by a restore.

### Restore the live database (an incident)

1. Pick the backup: the newest one from before the problem (`ls /var/backups/eos/daily/ weekly/`).
2. `eos-db-restore --check <file>` first, to see that it holds what you expect.
3. `eos-db-restore <file>` and type `restore eos` when asked. It takes a safety backup of the current
   database, stops the API, replaces the database, prints the row counts and starts the API again.
4. Open `/api/v1/health` and sign in to confirm. Everything written after that backup is gone; tell
   the affected organisations.

From another machine (the host itself is lost): deploy the API on a new host (`infra/docker/README.md`),
copy the dump from the second location, then step 3.

### Second location

**Until `EOS_BACKUP_OFFSITE` is set, the backups sit on the same disk as the database**, so a failed
disk or a deleted container loses both. Set it in `/etc/eos/db-backup.env` to an rsync destination:
a mounted folder (`/mnt/backup/eos/`) or another server over SSH (`backup@<host>:/srv/eos-backups/`,
with the root SSH key of the API host allowed there). Copies are never deleted on the destination by
this script, so a wiped local disk cannot wipe them too; prune them there.

Proxmox's own backup of the whole container (vzdump, the container's Backup tab) complements this:
it restores the whole machine, while `eos-db-restore` restores just the database, from any point in
the last two weeks, without stopping the container.

### Disk

The API container's root disk is small. A fresh database dumps to well under a megabyte; check
`du -sh /var/backups/eos` as data grows and lower `EOS_BACKUP_KEEP_DAILY` or grow the disk before it fills.
