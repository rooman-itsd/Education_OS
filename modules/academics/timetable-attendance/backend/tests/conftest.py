"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. The database
is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a shell that points at a real
database can never be reached from these tests. It is set here, before any test imports eos_core."""

import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/timetable_attendance_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))
