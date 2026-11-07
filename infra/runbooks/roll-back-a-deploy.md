# Roll back a deploy

How code gets to a host (`../autodeploy/README.md`):

| | Staging | Production |
|---|---|---|
| Follows | every merge to `main` (API every 2 minutes, web every minute) | the highest release tag `vX.Y.Z` |
| Roll back by | reverting the commit on `main` | tagging the last good commit with the next patch number |

**Who decides:** the lead for production (only the lead can push release tags: a ruleset on `v*` enforces it).
Anyone with merge rights may revert on `main` for staging.

**The database is not rolled back.** Migrations only go forward. A rollback of the code runs the old code against
the newer tables, which is fine for added columns and tables, and wrong if the bad release changed or removed
something the old code needs: read the release's migrations (`git diff v<good>..v<bad> -- '*/migrations/*'`) before
you roll back. Restore the database only for data loss, never as a way to "undo" a deploy ([restore.md](restore.md)).

## Production

**1. Find the last good release and what is live now.**

```
git fetch --tags
git tag --sort=-v:refname | head -5
curl -s https://educationos.futureacad.ae/VERSION
```

**2. The lead tags the last good commit with the next patch number.** If `v1.0.0` is bad and `v0.9.0`'s commit
`<good>` was fine, the new tag is `v1.0.1`:

```
git tag v1.0.1 <good>
git push origin v1.0.1
```

Never delete or move a published tag: hosts that already fetched it would keep it. (The one exception is a tag that
was refused because its commit is not on `main`: nothing deployed it, so delete it with
`git push origin :refs/tags/<tag>` and tag the right commit.)

**3. Wait, or hurry it along.** GitHub builds and tests the tag and publishes the web build; the web host serves it
within a minute and the API host deploys it within two. To deploy the API now, on the API host:

```
FORCE=1 eos-api-autodeploy
```

**4. Check.**

```
journalctl -t eos-api-autodeploy -n 20 --no-pager
curl -s http://127.0.0.1:8000/api/v1/health
curl -s https://educationos.futureacad.ae/VERSION
```

`/VERSION` must read the new tag; `health` must answer `ok`; the next `eos-monitor` minute must pass.

## Staging

Revert the bad commit on `main` through a pull request (`git revert <sha>`), merge it, and the next check deploys it.
A migration that fails is logged (`migrations failed at <sha>; API not restarted, staying on <sha>`): the API stays
on the previous version and the host tries again every two minutes, so fix forward or revert.

## If the deploy itself is stuck

```
cd /opt/education-os
journalctl -t eos-api-autodeploy -n 40 --no-pager
systemctl list-timers 'eos-api*' --no-pager
```

A deploy that fails to build, or whose migrations fail, leaves the running containers as they were and tries again
on the next check. `df -h /` first: a full disk is the usual cause (`docker builder prune -af` frees the build cache).
