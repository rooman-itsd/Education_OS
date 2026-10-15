"""Run once inside the API image after the first start: the API created the schema from its models
(init_db), so record each platform service's Alembic chain as being at head. Skips chains that already
have a version table. Used by tools/scripts/deploy-api-lxc.sh."""

import os
import subprocess

from sqlalchemy import create_engine, inspect

names = set(inspect(create_engine(os.environ["EOS_DATABASE_URL"])).get_table_names())
for service in ("identity", "tenancy", "billing"):
    if f"{service}_alembic_version" in names:
        print(f"{service}: chain already recorded")
        continue
    subprocess.run(["alembic", "stamp", "head"], cwd=f"platform/{service}/db", check=True)
    print(f"{service}: stamped head")
