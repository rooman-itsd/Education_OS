#!/bin/sh
# The one migration path (docker-compose.api.yml `migrate`, which the API waits for; the API auto-deploy runs
# the same service). Runs inside the API image as the database owner, in this order:
#   1. db-roles.py         the eos_app role the API connects as: row access only, no DDL
#   2. stamp-chains.py     only for a database whose tables the API created before migrations existed
#   3. alembic upgrade     every chain apps/backend/config/modules.enabled.yaml enables, platform first
#   4. init_db             outbox_event, the one table with no chain yet; goes when it gets an event-bus chain
set -eu
cd /repo
python infra/docker/db-roles.py
python infra/docker/stamp-chains.py
for chain in $(python tools/scripts/enabled-modules.py chains); do
  (cd "$chain" && alembic upgrade head)
done
python -c "from eos_core.db import init_db; init_db()"
echo "migrate: done"
