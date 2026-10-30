import os
import tempfile
from pathlib import Path

# A throwaway SQLite file, set before eos_core.db builds its engine from the setting; the repo root for plans.yaml.
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/billing-test.db")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))
