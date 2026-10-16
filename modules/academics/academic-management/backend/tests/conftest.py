"""The module's tests run alone (module standard rule 6). Set before eos_core is imported: the database is always a
throwaway SQLite file and tokens are signed with a test key. Both are overwritten, not defaulted, so a shell that
points at a real database or holds a real key can never be reached from these tests."""

import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/academic_management_test.db"
os.environ["EOS_JWT_SECRET"] = "academic-management-tests-only-not-a-real-key-32b"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))
