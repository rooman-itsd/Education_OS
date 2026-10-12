#!/usr/bin/env python3
"""Migration check (module standard rule 11): every table a migration creates carries `organisation_id`
and gets a row-level-security policy on `app.organisation_id`.

Scans `db/migrations/**` (*.py Alembic revisions and *.sql) in every module, platform service and
integration. For each created table, the same file must

- declare an `organisation_id` column in the CREATE TABLE / op.create_table call, and
- enable RLS on it (`ALTER TABLE <t> ENABLE ROW LEVEL SECURITY`, or a call whose name contains `rls`
  with the table name as an argument, such as an eos_core helper), and
- create a policy for it that reads `app.organisation_id` (not needed when a `rls` helper call is used).

A table that genuinely holds no tenant data is exempted in the same file with a reviewed comment:
    # rls-exempt: <table>: <reason>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = {"node_modules", ".venv", "dist", ".git", "__pycache__"}

NAME = r"""["'`]?(?:[\w]+["'`]?\.["'`]?)?([A-Za-z_]\w*)["'`]?"""
PY_CREATE = re.compile(r"""\bop\.create_table\(\s*["']([A-Za-z_]\w*)["']""")
SQL_CREATE = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?" + NAME, re.I)
EXEMPT = re.compile(r"rls-exempt:\s*([A-Za-z_]\w*)\s*:\s*(\S.*)", re.I)


def migration_files(root: Path) -> list[Path]:
    found = []
    for base in ("modules", "platform", "integrations"):
        for path in (root / base).rglob("*"):
            if (
                path.suffix in (".py", ".sql")
                and "migrations" in path.parts
                and path.is_file()
                and not (SKIP & set(path.parts))
            ):
                found.append(path)
    return sorted(found)


def _call_body(text: str, start: int) -> str:
    """Text of the call or statement starting at `start`, up to its balanced closing parenthesis."""
    depth, i = 0, text.find("(", start)
    if i == -1:
        return text[start:]
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return text[start:]


def created_tables(text: str, suffix: str) -> list[tuple[str, str]]:
    """(table, definition) for every table the file creates."""
    if suffix == ".py":
        found = [(m.group(1), _call_body(text, m.start())) for m in PY_CREATE.finditer(text)]
        # raw SQL inside op.execute("CREATE TABLE ...") counts too
        found += [(m.group(1), _call_body(text, m.start())) for m in SQL_CREATE.finditer(text)]
        return found
    return [(m.group(1), _call_body(text, m.start())) for m in SQL_CREATE.finditer(text)]


def has_rls(text: str, table: str) -> tuple[bool, bool]:
    """(rls enabled, policy on app.organisation_id) for `table` anywhere in the file."""
    t = re.escape(table)
    on_table = r"""(?:["'`]?\w+["'`]?\.)?["'`]?""" + t + r"""["'`]?"""
    enabled = re.search(r"ALTER\s+TABLE\s+(?:ONLY\s+)?" + on_table + r"\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY", text, re.I)
    helper = re.search(r"\w*rls\w*\s*\([^)]*[\"']" + t + r"[\"']", text, re.I)
    if helper:
        return True, True
    policy = re.search(r"CREATE\s+POLICY\s+\w+\s+ON\s+" + on_table + r"[\s\S]{0,600}?app\.organisation_id", text, re.I)
    return bool(enabled), bool(policy)


def check_file(path: Path, root: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    where = path.relative_to(root).as_posix()
    exempt = {m.group(1) for m in EXEMPT.finditer(text)}
    problems = []
    seen = set()
    for table, definition in created_tables(text, path.suffix):
        if table in seen or table in exempt:
            continue
        seen.add(table)
        if "organisation_id" not in definition:
            problems.append(f"{where}: table `{table}` has no organisation_id column")
        enabled, policy = has_rls(text, table)
        if not enabled:
            problems.append(f"{where}: table `{table}` does not enable row level security")
        if not policy:
            problems.append(f"{where}: table `{table}` has no policy on app.organisation_id")
    return problems


def check(root: Path) -> list[str]:
    problems = []
    for path in migration_files(root):
        problems += check_file(path, root)
    return problems


def main() -> int:
    problems = check(ROOT)
    if problems:
        print("Migration check failed (module standard rule 11: organisation_id and RLS on every table):")
        print("\n".join(problems))
        print("A table with no tenant data needs a reviewed `# rls-exempt: <table>: <reason>` comment.")
        return 1
    print(f"migration check ok ({len(migration_files(ROOT))} migration files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
