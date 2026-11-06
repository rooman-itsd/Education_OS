# Disaster recovery: rebuild the API host (#151)

The API host (the `education-os` container: API, relay, scheduler, Postgres, Keycloak when on) is lost: its disk
failed, it was deleted, or it cannot be trusted. This rebuilds it on a **new container** from the repository and
the newest database backup, and is run as a **timed drill** every quarter so the steps and the time are known
before they are needed.

**Objective** (agreed with the lead on 3 Nov 2026, #345): back in service within **2 hours** (RTO), losing at most
the changes since the last nightly backup, **24 hours** (RPO). A nightly dump cannot do better than 24 hours;
point-in-time recovery, which would, is planned for v1.1. A drill is timed against the 2 hours: its **Total** in the
drill log must stay under it, and a drill that does not is an incident like a failed restore.

## Before you need it

Without these the rebuild cannot start. Check them at every drill.

| Needed | Where it is | Check |
|---|---|---|
| A recent backup **off the lost host** | `EOS_BACKUP_OFFSITE` (README, "Second location"): a different physical machine over SSH, never a container on the same Proxmox host, since one disk failure would take both. Until it is set, Proxmox's nightly container backup (vzdump) to a second storage is the fallback | `ls` the destination: a dump from last night |
| **How a new host reaches that backup** | in the password manager with `.env.api`: the `EOS_BACKUP_OFFSITE` value (a mounted folder, or `user@host:/path`) and who can add a key at the destination. The setting lives in `/etc/eos/db-backup.env` and the destination trusts **the old host's** SSH key, both lost with the host | the destination's admin is reachable, and knows the procedure in step 3 |
| `.env.api` (the secrets) | a copy in the team's password manager, kept by the lead. Not in git, not in the backups | the copy's `EOS_JWT_SECRET` matches the host's |
| Proxmox access | root SSH (`root@<proxmox-ip>`) or the web console's Shell, to create the container and copy files | `pveversion` |
| A free LAN IP and container id | the lead | |

Without the `.env.api` copy the host still comes back with new secrets, but everyone has to sign in again, and
the SMTP password, Sentry DSN and alert webhook must be fetched again from their services.

## The rebuild

Write the time at the start of each step into the drill log below. `<ctid>` and `<ip>` are the new container's;
`<old-ctid>` is the lost one's (122 on staging).

**1. Create the container and deploy the API** (from a laptop with Proxmox access, in the repository).
For a drill, `WIRE_PROXY=0` keeps the live site on the old host; for a real incident leave it out, and step 6 is
done here.

```
PVE_HOST=root@<proxmox-ip> CTID=<ctid> CT_IP=<ip> CT_HOSTNAME=education-os-dr WIRE_PROXY=0 \
EOS_SUPER_ADMIN_EMAIL=<email> EOS_SUPER_ADMIN_PASSWORD=<password> \
tools/scripts/deploy-api-lxc.sh
```

With only the Proxmox web console (node > Shell, as root), run it there instead, from a clone of the
repository (a download: nothing is installed on the Proxmox host); `PVE_HOST=local` needs no SSH, and `SSH_PUBKEY` is your `.pub` key pasted into a file:

```
mkdir /root/eos-dr && curl -fsSL https://github.com/rooman-itsd/Education_OS/archive/refs/heads/main.tar.gz | tar xz -C /root/eos-dr --strip-components=1 && cd /root/eos-dr
nano /root/admin.pub                      # paste your public key (the .pub file), save
read -rp 'super admin email: ' EOS_SUPER_ADMIN_EMAIL; read -rsp 'super admin password: ' EOS_SUPER_ADMIN_PASSWORD; echo
export EOS_SUPER_ADMIN_EMAIL EOS_SUPER_ADMIN_PASSWORD
PVE_HOST=local SSH_PUBKEY=/root/admin.pub CTID=<ctid> CT_IP=<ip> CT_HOSTNAME=education-os-dr WIRE_PROXY=0 \
bash tools/scripts/deploy-api-lxc.sh
```

It creates a Debian container with Docker, clones `main`, generates a new `.env.api`, builds, migrates and starts
every service, and installs the auto-deploy and the nightly backup. Ends with `done: the API runs in container`.

**2. Put the saved secrets back** (skip in a drill, unless the copy itself is being tested). On the new host,
`nano /opt/education-os/infra/docker/.env.api` and replace these lines with the saved copy's: `EOS_JWT_SECRET`
(sessions stay valid), `EOS_SUPER_ADMIN_*`, `EOS_DEV_MODE`, `EOS_CORS_ORIGINS`, the mail (`NOTIFICATION_*`,
`MESSAGING_PROVIDERS_*`), `EOS_SENTRY_DSN`, `EOS_ENVIRONMENT`, `EOS_LOG_FORMAT`, `EOS_LOG_LEVEL`, `COMPOSE_PROFILES`,
`KEYCLOAK_ADMIN*`, `KC_HOSTNAME` and `EOS_OIDC_*`.
**Keep the new host's** `EOS_DB_PASSWORD`, `EOS_APP_DB_PASSWORD`, `KEYCLOAK_DB_PASSWORD` and `KEYCLOAK_BIND`: the
new databases were created with those. Then:
`cd /opt/education-os && docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d`.

**In a drill, never copy the mail settings, `EOS_SENTRY_DSN` or the alert webhook to the drill host.** It restores
real data, and its relay delivers the restored outbox: with a working SMTP relay it would send real mail to real
people (trial reminders, verification mails) from the drill. The generated `.env.api` has none of them; keep it so.

**3. Copy the newest backup to the new host.** The dump holds personal data: it goes from server to server,
never through a laptop disk.

*a) From the second location* (a real incident). The destination trusts the old host's key, so first let the new host
in: on the new host, make a key and print its public half,

```
ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_ed25519 -C "education-os-dr" && cat /root/.ssh/id_ed25519.pub
```

and the destination's admin adds that line to the backup user's `~/.ssh/authorized_keys` (a mounted folder needs
the mount instead). Then put the same `EOS_BACKUP_OFFSITE` value into the new host's `/etc/eos/db-backup.env`, so
its nightly backups continue there, and copy (on the new host):

```
mkdir -p /var/backups/eos/restore && rsync -a <offsite>/daily/<newest>.dump <offsite>/daily/<newest>.dump.sha256 /var/backups/eos/restore/
```

*b) If the second location cannot be reached:* restore the lost container's last Proxmox backup instead (vzdump; the
node's web UI, the container's Backup tab, Restore, as a new id), which brings back the whole machine as of that
backup, then continue at step 5. Data written since that backup is lost.

*c) In a drill, where the old host is still there:* on the Proxmox host (`F` is the newest name from
`pct exec <old-ctid> -- ls /var/backups/eos/daily`):

```
F=eos-<time>.dump
pct exec <ctid> -- mkdir -p /var/backups/eos/restore
for f in "$F" "$F.sha256"; do
  pct pull <old-ctid> "/var/backups/eos/daily/$f" "/root/$f" && pct push <ctid> "/root/$f" "/var/backups/eos/restore/$f" --perms 600 ||
    { echo "copying $f failed: stop and fix it before step 4" >&2; rm -f "/root/$f"; break; }
  rm -f "/root/$f"
done
```

**4. Restore it** (on the new host). `--check` first: it proves the dump and prints the rows per table, to compare
with the old host's numbers. Then the real restore: type `restore eos` when asked. It stops the API, relay and
scheduler, replaces the database, migrates it to this code and starts them again.

```
eos-db-restore --check /var/backups/eos/restore/<file>.dump | tee /root/dr-check.txt; echo "exit: ${PIPESTATUS[0]}"
eos-db-restore /var/backups/eos/restore/<file>.dump | tee /root/dr-restore.txt; echo "exit: ${PIPESTATUS[0]}"
```

Both must end `exit: 0` (`tee` would hide the script's own status). If `pg_restore` itself fails half-way (`exit: 1`
without "Restored."), the services are started again anyway, on a half-restored database: stop them at once
(`docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api stop api relay scheduler`) and
run the restore again before anything else. A restore whose migrate step fails still starts
the services but ends `exit: 1` with an error: fix the migration before going on.

With Keycloak on (`COMPOSE_PROFILES=oidc`), restore its dump too (README, "Nightly database backup").

**5. Check it works** (on the new host):

```
curl -s http://127.0.0.1:8000/api/v1/health
cd /opt/education-os && docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api ps --all
diff <(grep -E '^  [^ ]+ [0-9]+$' /root/dr-check.txt) <(grep -E '^  [^ ]+ [0-9]+$' /root/dr-restore.txt) && echo "row counts identical"
grep -c "migrate: done" /root/dr-restore.txt
```

Health says `ok`; `db`, `api`, `relay` and `scheduler` are `Up` (`migrate` `Exited (0)`); `migrate: done` is in the
restore's output (the count is 1); the row counts are
identical; and a user who existed before signs in (from the LAN: `curl` the sign-in endpoint against
`http://<ip>:8000`, or step 6 first in an incident).

**6. Send the traffic there** (real incident only). Point the public `/api/` at the new host: re-run step 1's
command without `WIRE_PROXY=0`. That is not only the proxy step: on the existing container it resets the checkout to
`main`, keeps `.env.api`, rebuilds the image and restarts every service (a minute of downtime on the new host),
reinstalls the auto-deploy and backup timers (the backup install takes a backup at once, of the restored data),
and only then points `/api/` at it. Then `curl -s https://educationos.futureacad.ae/api/v1/health`.
Install the monitor (its `install.sh` arrives with #381; until that is merged the folder holds only a README):
`bash /opt/education-os/infra/monitoring/install.sh`.

**7. After a drill:** delete the drill container and the clone on the Proxmox host
(`pct stop <ctid> && pct destroy <ctid> && rm -rf /root/eos-dr /root/admin.pub`), so
no second copy of the data stays around, unless it is about to become another environment's host. Record the
times below, and open an issue for every step that went wrong.

## Drill log

A drill restores from the **offsite copy** onto a throwaway container the lead creates, and destroys it afterwards (step 7).
The Total must stay under the 2-hour RTO.

| Date | Who | Backup used | 1 deploy | 3 copy | 4 restore | 5 checks | Total | Notes |
|---|---|---|---|---|---|---|---|---|
