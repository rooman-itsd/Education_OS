# Disaster recovery: rebuild the API host (#151)

The API host (the `education-os` container: API, relay, scheduler, Postgres, Keycloak when on) is lost: its disk
failed, it was deleted, or it cannot be trusted. This rebuilds it on a **new container** from the repository and
the newest database backup, and is run as a **timed drill** every quarter so the steps and the time are known
before they are needed.

**Objective** (to be agreed with the lead, #151): back in service within **1 hour** (RTO), losing at most the
changes since the last nightly backup, **24 hours** (RPO).

## Before you need it

Without these the rebuild cannot start. Check them at every drill.

| Needed | Where it is | Check |
|---|---|---|
| A recent backup **off the lost host** | `EOS_BACKUP_OFFSITE` (README, "Second location"), else Proxmox's container backup | `ls` the destination: a dump from last night |
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
`MESSAGING_PROVIDERS_*`), `EOS_SENTRY_DSN`, `COMPOSE_PROFILES`, `KEYCLOAK_ADMIN*`, `KC_HOSTNAME` and `EOS_OIDC_*`.
**Keep the new host's** `EOS_DB_PASSWORD`, `EOS_APP_DB_PASSWORD`, `KEYCLOAK_DB_PASSWORD` and `KEYCLOAK_BIND`: the
new databases were created with those. Then:
`cd /opt/education-os && docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api up -d`.

**3. Copy the newest backup to the new host.** The dump holds personal data: it goes from server to server,
never through a laptop disk. From the second location (on the new host):

```
mkdir -p /var/backups/eos/restore && rsync -a <offsite>/daily/<newest>.dump <offsite>/daily/<newest>.dump.sha256 /var/backups/eos/restore/
```

or, in a drill where the old host is still there, on the Proxmox host (`F` is the newest name from
`pct exec <old-ctid> -- ls /var/backups/eos/daily`):

```
F=eos-<time>.dump
pct exec <ctid> -- mkdir -p /var/backups/eos/restore
for f in "$F" "$F.sha256"; do
  pct pull <old-ctid> "/var/backups/eos/daily/$f" "/root/$f" && pct push <ctid> "/root/$f" "/var/backups/eos/restore/$f" --perms 600
  rm -f "/root/$f"
done
```

**4. Restore it** (on the new host). `--check` first: it proves the dump and prints the rows per table, to compare
with the old host's numbers. Then the real restore: type `restore eos` when asked. It stops the API, relay and
scheduler, replaces the database, migrates it to this code and starts them again.

```
eos-db-restore --check /var/backups/eos/restore/<file>.dump | tee /root/dr-check.txt
eos-db-restore /var/backups/eos/restore/<file>.dump | tee /root/dr-restore.txt
```

With Keycloak on (`COMPOSE_PROFILES=oidc`), restore its dump too (README, "Nightly database backup").

**5. Check it works** (on the new host):

```
curl -s http://127.0.0.1:8000/api/v1/health
cd /opt/education-os && docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api ps --all
diff <(grep -E '^  [^ ]+ [0-9]+$' /root/dr-check.txt) <(grep -E '^  [^ ]+ [0-9]+$' /root/dr-restore.txt) && echo "row counts identical"
```

Health says `ok`; `db`, `api`, `relay` and `scheduler` are `Up` (`migrate` `Exited (0)`); the row counts are
identical; and a user who existed before signs in (from the LAN: `curl` the sign-in endpoint against
`http://<ip>:8000`, or step 6 first in an incident).

**6. Send the traffic there** (real incident only). Point the public `/api/` at the new host: re-run step 1's
command without `WIRE_PROXY=0` (every earlier step is skipped as already done), then
`curl -s https://educationos.futureacad.ae/api/v1/health`. Install the monitor:
`bash /opt/education-os/infra/monitoring/install.sh`.

**7. After a drill:** delete the drill container and the clone on the Proxmox host
(`pct stop <ctid> && pct destroy <ctid> && rm -rf /root/eos-dr /root/admin.pub`), so
no second copy of the data stays around, unless it is about to become another environment's host. Record the
times below, and open an issue for every step that went wrong.

## Drill log

| Date | Who | Backup used | 1 deploy | 3 copy | 4 restore | 5 checks | Total | Notes |
|---|---|---|---|---|---|---|---|---|
