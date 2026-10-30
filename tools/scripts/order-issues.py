#!/usr/bin/env python3
"""Give every roadmap issue one global sequence number and apply it everywhere.

Order: milestone M1..M5, then within a milestone week 1 -> foundation -> modules -> dashboards
(wave A, B, C, D) -> production, then issue number. The number is written as a "[NNN] " title
prefix, as the "Order" number field on project board #1, and as the item position on the board.
tools/scripts/next-issue.py hands out work in this same order.

Idempotent: re-run after adding issues. Needs a gh token with the project scope.
  order-issues.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

REPO = "rooman-itsd/Education_OS"
OWNER = "faizanrooman"
PROJECT = 1
PREFIX = re.compile(r"^\[\d+\]\s*")
KIND = [
    ("week-1", 0),
    ("phase:foundation", 1),
    ("type:module", 2),
    ("wave:A", 3),
    ("wave:B", 4),
    ("wave:C", 5),
    ("wave:D", 6),
    ("phase:production", 7),
]


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def gql(query: str) -> dict:
    return json.loads(gh("api", "graphql", "-f", f"query={query}"))


def kind_rank(labels: set[str]) -> int | None:
    return next((rank for label, rank in KIND if label in labels), None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    issues = json.loads(
        gh(
            "issue",
            "list",
            "-R",
            REPO,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,id,title,labels,milestone",
        )
    )
    ordered = []
    for it in issues:
        labels = {lab["name"] for lab in it["labels"]}
        rank = kind_rank(labels)
        ms = (it.get("milestone") or {}).get("title", "")
        if rank is None or not ms:
            continue  # not a roadmap issue (e.g. the pinned Start here)
        ordered.append((ms[:2], rank, it["number"], it))
    ordered.sort(key=lambda t: (t[0], t[1], t[2]))
    width = max(3, len(str(len(ordered))))

    # project ids
    proj = gql(
        f'{{ user(login:"{OWNER}"){{ projectV2(number:{PROJECT}){{ id fields(first:40){{ nodes{{ ... on ProjectV2FieldCommon {{ id name dataType }} }} }} }} }} }}'
    )["data"]["user"]["projectV2"]
    pid = proj["id"]
    order_field = next((f["id"] for f in proj["fields"]["nodes"] if f.get("name") == "Order"), None)
    if not order_field and not a.dry_run:
        order_field = gql(
            f'mutation {{ createProjectV2Field(input:{{projectId:"{pid}", dataType:NUMBER, name:"Order"}}) {{ projectV2Field {{ ... on ProjectV2FieldCommon {{ id }} }} }} }}'
        )["data"]["createProjectV2Field"]["projectV2Field"]["id"]

    prev_item = None
    renamed = 0
    for seq, (_ms, _rank, number, it) in enumerate(ordered, start=1):
        base = PREFIX.sub("", it["title"])
        title = f"[{seq:0{width}d}] {base}"
        if a.dry_run:
            print(title)
            continue
        if title != it["title"]:
            gh("issue", "edit", str(number), "-R", REPO, "--title", title)
            renamed += 1
        item = gql(
            f'mutation {{ addProjectV2ItemById(input:{{projectId:"{pid}", contentId:"{it["id"]}"}}) {{ item {{ id }} }} }}'
        )["data"]["addProjectV2ItemById"]["item"]["id"]
        gql(
            f'mutation {{ updateProjectV2ItemFieldValue(input:{{projectId:"{pid}", itemId:"{item}", fieldId:"{order_field}", value:{{number:{seq}}}}}) {{ projectV2Item {{ id }} }} }}'
        )
        after = f', afterId:"{prev_item}"' if prev_item else ""
        gql(
            f'mutation {{ updateProjectV2ItemPosition(input:{{projectId:"{pid}", itemId:"{item}"{after}}}) {{ items(first:1) {{ totalCount }} }} }}'
        )
        prev_item = item
    print(f"{len(ordered)} issues ordered, {renamed} titles changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
