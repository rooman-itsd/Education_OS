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
When Keycloak runs (ADR-0006, compose profile `oidc`), its own database is dumped in the same run as
`keycloak-<UTC time>.dump`, kept and pruned the same way. With the profile on and `kc-db` not running (or its
dump failing), the run still keeps and copies the API's dump, then logs `FAILED: ...` and exits 1 without
updating `last-success`, so a missing Keycloak backup is never silent. `eos-db-restore` restores the API's database
only; to restore Keycloak's, stop the `keycloak` service and run
`docker compose ... exec -T kc-db pg_restore -U keycloak -d keycloak --clean --if-exists < keycloak-<time>.dump`,
then start it again.
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

To prove the restored copy is the live data, compare its counts with the live database's (run right after a
fresh `eos-db-backup`, so nothing has changed in between):

```
time eos-db-backup
time eos-db-restore --check "$(ls -1 /var/backups/eos/daily/eos-*.dump | tail -1)" | tee /tmp/restore-check.txt
docker compose -f /opt/education-os/infra/docker/docker-compose.api.yml --env-file /opt/education-os/infra/docker/.env.api exec -T db psql -U eos -d eos -At <<'SQL' | sort > /tmp/live-counts.txt
SELECT format('SELECT %L || '' '' || count(*) FROM %I.%I', table_schema || '.' || table_name, table_schema, table_name)
FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1
\gexec
SQL
grep '^  ' /tmp/restore-check.txt | sed 's/^  //' | sort > /tmp/restored-counts.txt
diff /tmp/live-counts.txt /tmp/restored-counts.txt && echo "IDENTICAL: every table, every row count"
```

#### Drill log

Add a row after every drill. A restore that fails, or counts that differ, is an incident: open an issue.

| Date (UTC) | Host | Dump | Backup | Restore check | Result | Notes |
|---|---|---|---|---|---|---|
| 2026-10-30 | education-os (staging, CT 122) | `eos-2026-10-30T093023Z.dump`, 456 KB | 2.3 s | 7.2 s, 131 tables | Row counts identical to live (`diff` empty) | Staging holds almost no data (1 user, no organisation), so the timings say little about a real institution: repeat monthly and once organisations exist. No second location was set (`EOS_BACKUP_OFFSITE` empty), so the backups shared the database's disk; a full restore onto a clean host is the DR drill (#151). |

### Restore the live database (an incident)

1. Pick the backup: the newest one from before the problem (`ls /var/backups/eos/daily/ weekly/`).
2. `eos-db-restore --check <file>` first, to see that it holds what you expect.
3. `eos-db-restore <file>` and type `restore eos` when asked. It takes a safety backup of the current
   database, stops the API, the relay and the scheduler, replaces the database, prints the row counts, runs
   the migrations (a backup from older code is brought up to this checkout) and starts them again.
4. Open `/api/v1/health` and sign in to confirm. Everything written after that backup is gone; tell
   the affected organisations.

From another machine (the host itself is lost): follow [DR.md](DR.md), the timed rebuild on a new container,
which is also drilled every quarter.

### Second location

**Until `EOS_BACKUP_OFFSITE` is set, the backups sit on the same disk as the database**, so a failed
disk or a deleted container loses both. Set it in `/etc/eos/db-backup.env` to an rsync destination:
a mounted folder (`/mnt/backup/eos/`) or another server over SSH (`backup@<host>:/srv/eos-backups/`,
with the root SSH key of the API host allowed there). The destination keeps **the same dumps as the
local folders**: a dump pruned locally is deleted there on the same run. Two limits keep a wiped local
disk from wiping the second copy too: only this script's own files (`eos-*.dump`, `keycloak-*.dump` and
their `.sha256`) are ever deleted there, and a run that would delete more than
`EOS_BACKUP_OFFSITE_MAX_PRUNE` dumps (default 4, a normal night's rotation) deletes nothing, copies the
new dump and ends `FAILED`. After lowering the retention on purpose, let the destination catch up once:

```
EOS_BACKUP_OFFSITE_FORCE_PRUNE=1 eos-db-backup
```

**How long data stays in backups (DPDP).** With the defaults, a dump is kept 14 days as a daily and,
if it is a Sunday's, 8 weeks as a weekly, here and at the second location alike. So data deleted from
the database (an organisation purged by tenancy, a person's record removed) is gone from every backup
after at most 8 weeks; restoring a backup older than a purge would bring that organisation back, so a
restore after a purge must be followed by the purge again.

Proxmox's own backup of the whole container (vzdump, the container's Backup tab) complements this:
it restores the whole machine, while `eos-db-restore` restores just the database, from any point in
the last two weeks, without stopping the container.

### Disk

The API container's root disk is small. A fresh database dumps to well under a megabyte; check
`du -sh /var/backups/eos` as data grows and lower `EOS_BACKUP_KEEP_DAILY` or grow the disk before it fills.
