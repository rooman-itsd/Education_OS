# Runbooks (#150)

What to do, step by step, when something on the API host needs attention. Each runbook says when to use it, who
may decide, the exact commands, and how to check that it worked. They are written to be followed at night by a
person who has not seen the system for weeks: read one through before you start.

| Runbook | Use it when |
|---|---|
| [on-call.md](on-call.md) | An alert arrives (the Telegram group), or you are on call and want to know who does what |
| [restore.md](restore.md) | Data is lost or wrong in the database, or the whole host is lost |
| [suspend-a-tenant.md](suspend-a-tenant.md) | An organisation must be blocked at once, or switched back on (non-payment, abuse, a security incident) |
| [rotate-secrets.md](rotate-secrets.md) | A secret leaked, someone with access left, or on the regular schedule |
| [roll-back-a-deploy.md](roll-back-a-deploy.md) | A release or a merge to `main` broke the site |
| [scale-the-api.md](scale-the-api.md) | The API is slow or out of memory under load |

Not repeated here, because they already have a home: how the backup works (`../backup-dr/README.md`), rebuilding a
lost host (`../backup-dr/DR.md`), what each monitor check watches (`../monitoring/README.md`), and how staging and
production get their code (`../autodeploy/README.md`).

## Conventions

- Run server commands **as root on the API host** (the `education-os` container; staging is its own container),
  from the repository: `cd /opt/education-os`.
- Every command that talks to Docker Compose uses this prefix; each runbook sets it on its first line so you can
  paste the block as it is:

  ```
  C="docker compose -f infra/docker/docker-compose.api.yml --env-file infra/docker/.env.api"
  ```
- **Secrets never go in git, in chat, in a ticket or in a screenshot.** They live in `infra/docker/.env.api`
  and `/etc/eos/*.env` on the host, and in the team's password manager. Real addresses (IPs, phone numbers) are
  kept there too, not in these files.
- The public site is `https://educationos.futureacad.ae`; staging is `https://staging.educationos.futureacad.ae`.
  On the host, the API answers on `http://127.0.0.1:8000/api/v1/`, which works even when the public proxy does not.
- After any change on production, write one line in the team channel: what, when, who, and the result.
- A runbook that was wrong when you used it is a bug: fix it in a pull request the same day.
