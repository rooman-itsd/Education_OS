import os
import tempfile
from pathlib import Path

# Before eos_core.db is imported: its engine is built at import time from the setting, and without this it would
# point at the default database rather than a throwaway file.
os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/billing-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))
