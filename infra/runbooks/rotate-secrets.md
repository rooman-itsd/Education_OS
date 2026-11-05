# Rotate a secret

Rotate when a secret may have leaked, when someone who knew it leaves, and on the schedule below. Do one secret at
a time, and check the site after each.

**Who decides:** the lead for a leak or a person leaving; the host owner (Srujan) for the schedule.

**Before you start**
- Keep the way back: copy the current file first (`cp infra/docker/.env.api infra/docker/.env.api.bak`; delete the
  copy when you are done, it holds the old secrets).
- New values come from the shell, never from your head or a chat: `openssl rand -hex 32`.
- **When you finish, put the new value in the team's password manager** (`.env.api` is in no backup). A secret changed
  on the host and not saved there is lost with the host.
- Never paste a secret into chat, a ticket, a pull request or a screenshot.

Each block below starts from the repository on the API host:

```
cd /opt/education-os
C="docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api"
```

## Schedule (proposed)

| Secret | At least every | Also when |
|---|---|---|
| `EOS_JWT_SECRET` | 12 months | a leak; anyone with `.env.api` leaves |
| `EOS_APP_DB_PASSWORD`, `EOS_DB_PASSWORD` | 12 months | a leak; anyone with `.env.api` leaves |
| SMTP password, Sentry DSN, alert bot token | 12 months | the provider reports a leak; a person leaves |
| Offsite backup key, Proxmox root password and keys | 12 months | a person with access leaves |

## 1. `EOS_JWT_SECRET` (signs every sign-in token)

**Effect: every user is signed out** and must sign in again. Do it outside working hours unless it is a leak.

```
nano infra/docker/.env.api      # replace the EOS_JWT_SECRET value with the output of: openssl rand -hex 32
$C up -d api relay scheduler
```

Check: `curl -s http://127.0.0.1:8000/api/v1/health`, then sign in on the site.

## 2. `EOS_APP_DB_PASSWORD` (the API's database login, role `eos_app`)

The migrate step sets the role's password from this value on every deploy, so change it and run the step:

```
nano infra/docker/.env.api      # replace the EOS_APP_DB_PASSWORD value
$C run --rm migrate
$C up -d api relay scheduler
```

Check: health `ok`, sign in, and `$C logs --tail 20 api` shows no authentication error.

## 3. `EOS_DB_PASSWORD` (the database owner, `eos`)

Postgres reads this value only when its data volume is first created, so changing the file alone changes nothing,
and changing the file before the database would break the migrate step. Change the database first, then the file:

```
NEW=$(openssl rand -hex 32)
$C exec -T db psql -U eos -d eos -c "ALTER USER eos PASSWORD '$NEW'"
sed -i "s/^EOS_DB_PASSWORD=.*/EOS_DB_PASSWORD=$NEW/" infra/docker/.env.api
unset NEW
$C run --rm migrate && echo "migrate ok"
```

The `db` container still holds the old value in its settings: the next `$C up -d` recreates it (the data stays;
the API is down for a few seconds), so run `$C up -d` yourself in a quiet hour rather than leave it to a deploy.

Check: `systemctl start eos-db-backup.service`, then `journalctl -u eos-db-backup.service -n 5 --no-pager` shows `ok`.
The new value is in `.env.api` only: copy it to the password manager now.

## 4. SMTP password (`MESSAGING_PROVIDERS_SMTP_PASSWORD`)

1. Change the password at the mail provider first (or create a second one, switch, then remove the old).
2. `nano infra/docker/.env.api`, replace the value.
3. `$C up -d api relay`
4. Check: `$C logs --since 5m relay | tail`, then trigger one real email (the lead can register a test organisation)
   and confirm it arrives. A wrong password shows as `535` or `authentication` in the relay's log.

## 5. Sentry DSN (`EOS_SENTRY_DSN`)

1. In the Sentry project, create a new DSN key, then disable the old one.
2. `nano infra/docker/.env.api`, replace `EOS_SENTRY_DSN`.
3. `$C up -d api relay scheduler`. Check that the next error appears in Sentry (the lead can cause a harmless one).

## 6. Alert bot (`EOS_MONITOR_WEBHOOK_URL` in `/etc/eos/monitor.env`)

1. In Telegram, ask BotFather to revoke the bot's token and issue a new one (`/revoke`).
2. Edit the file, with the whole URL **in double quotes** (an `&` cuts an unquoted line):
   `nano /etc/eos/monitor.env`
3. `systemctl start eos-monitor.service; journalctl -t eos-monitor -n 5 --no-pager`
4. Check that the group receives a message: stop the scheduler for a minute (`../monitoring/README.md`, "Test an alert").

## 7. The offsite backup key

The host's key lets it write to the second machine. Add the new one before removing the old, so a night's backup is
never left without a way in.

```
ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_ed25519.new -C "eos-backup@$(hostname)"
cat /root/.ssh/id_ed25519.new.pub
```

1. Send **only that `.pub` line** to the admin of the second machine; they add it to the backup user's
   `authorized_keys` with the same restrictions as the old one.
2. Swap the files: `mv /root/.ssh/id_ed25519 /root/.ssh/id_ed25519.old && mv /root/.ssh/id_ed25519.new /root/.ssh/id_ed25519 && mv /root/.ssh/id_ed25519.new.pub /root/.ssh/id_ed25519.pub`
3. `systemctl start eos-db-backup.service; journalctl -u eos-db-backup.service -n 5 --no-pager` ends in `copied to ...`.
4. Ask the admin to remove the old line, then `shred -u /root/.ssh/id_ed25519.old`.

## 8. Proxmox root password and SSH keys

Keep a second session open while you do this: a mistake here can lock you out.

1. In the Proxmox shell: `passwd root`, and save the new password in the password manager.
2. Make sure sign-in by key works in a **new** window before turning passwords off.
3. Allow keys only: in `/etc/ssh/sshd_config` set `PasswordAuthentication no`, then `sshd -t && systemctl reload ssh`.
4. Remove the keys of anyone who left from `/root/.ssh/authorized_keys`.

## What cannot be rotated from here yet

- **The super admin's password.** `EOS_SUPER_ADMIN_PASSWORD` only creates the first super admin; changing it later
  changes nothing for an account that exists. No endpoint in the identity API changes an existing password yet
  (checked on 5 Nov 2026). Until one exists, tell the lead if that password may have leaked.
- **Keycloak admin and database passwords** (`KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_PASSWORD`) matter only when
  single sign-on is switched on (`COMPOSE_PROFILES=oidc`). Add them here when it is.
