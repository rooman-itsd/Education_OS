"""Run inside the API image before migrating: record as "at head" every enabled Alembic chain whose tables
the API already created from its models at start-up (init_db), so `alembic upgrade head` does not try to
create them again. A chain with a version table is left alone, and a chain whose tables do not exist yet is
left for `alembic upgrade head` to create (with its row-level-security policies).

The chains are the ones apps/backend/config/modules.enabled.yaml enables (tools/scripts/enabled-modules.py):
platform services first, then modules and integrations. Used by tools/scripts/deploy-api-lxc.sh and the API
auto-deploy (infra/autodeploy/eos-api-autodeploy.sh)."""

import importlib.util
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def say(message: str) -> None:
    # stdout, not logging: each chain's env.py reconfigures logging and silences other loggers
    sys.stdout.write(f"stamp-chains: {message}\n")
    sys.stdout.flush()


ROOT = Path(os.environ.get("EOS_REPO_ROOT", "/repo"))
spec = importlib.util.spec_from_file_location("enabled_modules", ROOT / "tools/scripts/enabled-modules.py")
enabled_modules = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = enabled_modules
spec.loader.exec_module(enabled_modules)

url = os.environ["EOS_DATABASE_URL"]
names = set(inspect(create_engine(url)).get_table_names())
for entry in enabled_modules.entries(root=ROOT):
    if entry.chain is None:
        continue
    version_table = f"{entry.prefix}alembic_version"
    if version_table in names:
        say(f"{entry.name}: chain already recorded")
        continue
    if not any(n.startswith(entry.prefix) and n != version_table for n in names):
        say(f"{entry.name}: no tables yet; alembic upgrade head creates them")
        continue
    cfg = Config(str(entry.chain / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    command.stamp(cfg, "head")
    say(f"{entry.name}: stamped head")
