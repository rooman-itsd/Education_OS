"""Run once inside the API image after the first start: the API created the schema from its models
(init_db), so record each platform service's Alembic chain as being at head. Skips chains that already
have a version table. Used by tools/scripts/deploy-api-lxc.sh."""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("stamp-chains")

url = os.environ["EOS_DATABASE_URL"]
names = set(inspect(create_engine(url)).get_table_names())
for service in ("identity", "tenancy", "billing"):
    if f"{service}_alembic_version" in names:
        log.info("%s: chain already recorded", service)
        continue
    cfg = Config(str(Path("platform") / service / "db" / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    command.stamp(cfg, "head")
    log.info("%s: stamped head", service)
