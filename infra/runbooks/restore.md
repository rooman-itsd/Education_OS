# Restore

Two different situations. Decide which first.

| Situation | Go to |
|---|---|
| The host is fine, but the **database** is lost, corrupted or has wrong data (a bad migration, a mistaken bulk change) | [A. Restore the database on this host](#a-restore-the-database-on-this-host) |
| The **host itself** is lost (disk failed, container deleted, cannot be trusted) | `../backup-dr/DR.md`: it rebuilds on a new container, is timed against the **2-hour recovery objective**, and was drilled once |

The data you can get back is the last nightly backup: up to **24 hours** of changes are lost (the recovery
point objective). A restore replaces everything in the database, every organisation's data, not just one's.
Get the lead's agreement first unless the site is already down.

## A. Restore the database on this host

```
cd /opt/education-os
ls -lh /var/backups/eos/daily | tail -5
```

Use the newest dump from **before** the damage. If the damage is recent, that is the last one in the list; if it
happened earlier, set `F` to an older file by hand. Call it `F`.

**1. Prove it first.** This restores into a throwaway database, counts the rows in every table and drops it again;
live data is not touched.

```
F=$(ls -1 /var/backups/eos/daily/eos-*.dump | tail -1); echo "using: $F"
eos-db-restore --check "$F" | tee /root/restore-check.txt; echo "exit: ${PIPESTATUS[0]}"
```

Continue only on `exit: 0`. If the check fails, try the next older dump, or the offsite copy (below).

**2. Restore.** Type `restore eos` when asked. It takes a safety backup of the current database first, stops the API,
relay and scheduler, replaces the database, migrates it to this code and starts them again.

```
eos-db-restore "$F" | tee /root/restore.txt; echo "exit: ${PIPESTATUS[0]}"
```

**3. Check.**

```
curl -s http://127.0.0.1:8000/api/v1/health
journalctl -t eos-monitor --since "5 minutes ago" --no-pager | tail
```

Then sign in as a super admin on the site and open the organisations list. Write down the time of the dump you used.

### If the local dumps are gone or damaged: use the offsite copy

The second location is `EOS_BACKUP_OFFSITE` in `/etc/eos/db-backup.env`. Copy the newest dump and its checksum back and
verify it, then restore it as above:

```
set -a; . /etc/eos/db-backup.env; set +a
mkdir -p /var/backups/eos/restore
F=$(rsync "${EOS_BACKUP_OFFSITE%/}/daily/" | awk '/\.dump$/ {print $NF}' | sort | tail -1); echo "newest: $F"
rsync -a "${EOS_BACKUP_OFFSITE%/}/daily/$F" "${EOS_BACKUP_OFFSITE%/}/daily/$F.sha256" /var/backups/eos/restore/
(cd /var/backups/eos/restore && sha256sum -c "$F.sha256")
F="/var/backups/eos/restore/$F"
```

### After a restore: people whose data was purged

A restore older than a purge brings that organisation back. The retention rule means purged data is gone from every
backup after at most 8 weeks, but inside that window **run the purge again** for any organisation that was purged
after the dump was taken (`../backup-dr/README.md`, "How long data stays in backups"). Ask the lead for the list.

## Practice

`eos-db-restore --check` on the newest dump, monthly, and the full host rebuild once a quarter (`../backup-dr/DR.md`).
Both are written in the drill log there.
