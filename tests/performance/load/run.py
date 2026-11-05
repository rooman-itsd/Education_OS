"""Load test for the Education OS API (#152): sign-in, the Organisation Admin dashboard and registration, across many
organisations, with the results checked against the service level objectives in ../slo.yaml.

Run it against a stack started for the purpose (../README.md), never against production: it registers organisations.
It refuses to start unless the API reports dev_mode, which production never has, and it names everything it creates
`load-<run>-...`, so a run is easy to find and purge.

    python tests/performance/load/run.py --base http://127.0.0.1:18000 --orgs 50 --stages 10,25,50 --seconds 30

The super admin approves the organisations it registers: EOS_SUPER_ADMIN_EMAIL and EOS_SUPER_ADMIN_PASSWORD must be
in the environment (the same values as the stack's .env.api). Exit status 0 when every objective is met at the
objectives' concurrency, 1 when one is missed, 2 when the run could not start.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import secrets
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml

# What the Organisation Admin dashboard asks for when it opens: the shell's /me, then each widget's GET
# (platform/{billing,identity,audit,tenancy}/frontend/src/api). A browser sends them together, so a virtual user does too.
DASHBOARD = (
    "/identity/auth/me",
    "/billing/plans",
    "/billing/subscription",
    "/billing/invoices",
    "/tenancy/organisation/entitlement",
    "/identity/users",
    "/audit/records?limit=5",
)
PASSWORD = "Load-test-" + secrets.token_hex(6)
BROWSER_CONNECTIONS = 6


def say(line: str = "") -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


@dataclass
class Account:
    email: str
    slug: str
    token: str = ""


@dataclass
class Sample:
    """One scenario at one concurrency: every request's time in ms and its outcome."""

    scenario: str
    concurrency: int
    seconds: float = 0.0
    times: list[float] = field(default_factory=list)
    errors: int = 0  # 5xx, timeouts, refused connections: the API failed
    rejected: int = 0  # other non-2xx: the API answered, but not with success
    by_path: dict[str, list[float]] = field(default_factory=dict)

    def add(self, ms: float, status: int | None, path: str = "") -> None:
        self.times.append(ms)
        if path:
            self.by_path.setdefault(path, []).append(ms)
        if status is None or status >= 500:
            self.errors += 1
        elif status >= 400:
            self.rejected += 1

    def summary(self) -> dict:
        n = len(self.times)
        return {
            "scenario": self.scenario,
            "concurrency": self.concurrency,
            "requests": n,
            "rps": round(n / self.seconds, 1) if self.seconds else 0.0,
            "p50_ms": pct(self.times, 50),
            "p95_ms": pct(self.times, 95),
            "p99_ms": pct(self.times, 99),
            "max_ms": round(max(self.times), 1) if n else 0.0,
            "error_rate": round(self.errors / n, 4) if n else 0.0,
            "rejected": self.rejected,
            "p95_by_path_ms": {p: pct(t, 95) for p, t in sorted(self.by_path.items())},
        }


def pct(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))], 1)


async def timed(client: httpx.AsyncClient, method: str, path: str, **kw) -> tuple[float, httpx.Response | None]:
    start = time.perf_counter()
    try:
        r = await client.request(method, path, **kw)
    except httpx.HTTPError:
        r = None
    return (time.perf_counter() - start) * 1000, r


async def ok(client: httpx.AsyncClient, method: str, path: str, **kw) -> dict:
    r = await client.request(method, path, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code} {r.text[:200]}")
    return r.json()


async def sign_in(client: httpx.AsyncClient, email: str, password: str, slug: str | None = None) -> str:
    body = {"email": email, "password": password, **({"organisation_slug": slug} if slug else {})}
    return (await ok(client, "POST", "/identity/auth/login", json=body))["token"]


def registration(run: str, label: str) -> dict:
    slug = f"load-{run}-{label}"
    return {
        "organisation_name": f"Load test {run} {label}",
        "slug": slug,
        "academy_type": "engineering-college",
        "admin": {"name": "Load Admin", "email": f"admin@{slug}.example.com", "password": PASSWORD},
        "accepted_terms": True,
    }


async def seed(client: httpx.AsyncClient, run: str, orgs: int, root: str) -> list[Account]:
    """Register, verify and approve `orgs` organisations, a few at a time, and sign their admins in."""
    gate = asyncio.Semaphore(5)

    async def one(i: int) -> Account:
        async with gate:
            data = registration(run, f"{i:03d}")
            org = await ok(client, "POST", "/tenancy/register", json=data)
            await ok(client, "POST", "/tenancy/register/verify", json={"token": org["verification_token"]})
            await ok(
                client,
                "POST",
                f"/tenancy/admin/organisations/{org['id']}/approve",
                headers={"Authorization": f"Bearer {root}"},
                json={"reason": "load test"},
            )
            account = Account(email=data["admin"]["email"], slug=data["slug"])
            account.token = await sign_in(client, account.email, PASSWORD, account.slug)
            return account

    return list(await asyncio.gather(*(one(i) for i in range(orgs))))


def client_for(base: str, users: int) -> httpx.AsyncClient:
    # Enough connections that no request waits inside this script for one (the wait would be timed as the API's): a
    # browser opens up to six per site, and a dashboard sends seven requests at once.
    conns = users * BROWSER_CONNECTIONS + 20
    limits = httpx.Limits(max_connections=conns, max_keepalive_connections=conns)
    return httpx.AsyncClient(base_url=base.rstrip("/") + "/api/v1", timeout=30.0, limits=limits)


async def part(base: str, name: str, users: int, first_user: int, seconds: float, accounts: list, run: str) -> Sample:
    """One process's share of a scenario: `users` virtual users, numbered from `first_user`, each repeating the
    scenario's request(s) until the time is up."""
    sample = Sample(name, users)
    made = {"n": 0}
    tag = secrets.token_hex(2)  # registrations of this part, so a later stage never reuses an earlier stage's slug
    async with client_for(base, users) as client:

        async def signin(u: int) -> None:
            # The password travels with the accounts: a spawned process would draw a different PASSWORD of its own.
            email, slug, _, password = accounts[(u + len(sample.times)) % len(accounts)]
            body = {"email": email, "password": password, "organisation_slug": slug}
            ms, r = await timed(client, "POST", "/identity/auth/login", json=body)
            sample.add(ms, r.status_code if r else None)

        async def dashboard(u: int) -> None:
            auth = {"Authorization": f"Bearer {accounts[u % len(accounts)][2]}"}
            results = await asyncio.gather(*(timed(client, "GET", p, headers=auth) for p in DASHBOARD))
            for path, (ms, r) in zip(DASHBOARD, results, strict=True):
                sample.add(ms, r.status_code if r else None, path.split("?")[0])

        async def register(u: int) -> None:
            made["n"] += 1
            ms, r = await timed(client, "POST", "/tenancy/register", json=registration(run, f"{tag}-u{u}-{made['n']}"))
            sample.add(ms, r.status_code if r else None)

        work = {"signin": signin, "dashboard": dashboard, "registration": register}[name]
        start = time.perf_counter()
        stop = start + seconds

        async def user(u: int) -> None:
            while time.perf_counter() < stop:
                await work(u)

        await asyncio.gather(*(user(first_user + i) for i in range(users)))
        sample.seconds = time.perf_counter() - start
    return sample


def part_in_process(*args) -> Sample:
    return asyncio.run(part(*args))


def scenario(base: str, name: str, users: int, seconds: float, accounts: list, run: str, processes: int) -> Sample:
    """`users` virtual users split over `processes` load-generating processes. One Python process tops out at a few
    dozen requests a second, so more processes keep the generator from being the thing that is measured."""
    n = max(1, min(processes, users))
    shares = [users // n + (1 if i < users % n else 0) for i in range(n)]
    firsts = [sum(shares[:i]) for i in range(n)]
    args = [(base, name, shares[i], firsts[i], seconds, accounts, run) for i in range(n)]
    with ProcessPoolExecutor(max_workers=n, mp_context=multiprocessing.get_context("spawn")) as pool:
        parts = list(pool.map(part_in_process, *zip(*args, strict=True)))
    merged = Sample(name, users)
    for p in parts:
        merged.times += p.times
        merged.errors += p.errors
        merged.rejected += p.rejected
        for path, times in p.by_path.items():
            merged.by_path.setdefault(path, []).extend(times)
        merged.seconds = max(merged.seconds, p.seconds)
    return merged


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:18000", help="the API's address, without /api/v1")
    ap.add_argument("--orgs", type=int, default=50)
    ap.add_argument("--stages", default="10,25,50", help="concurrent users per stage, comma-separated")
    ap.add_argument("--seconds", type=float, default=30.0, help="length of each scenario at each stage")
    ap.add_argument("--slo", default=str(Path(__file__).resolve().parent.parent / "slo.yaml"))
    ap.add_argument("--out", default="", help="write the results as JSON here")
    ap.add_argument("--label", default="", help="a note stored with the results, e.g. 'pooler on'")
    ap.add_argument("--processes", type=int, default=4, help="load-generating processes the users are split over")
    a = ap.parse_args()
    stages = [int(s) for s in a.stages.split(",") if s.strip()]
    slo = yaml.safe_load(Path(a.slo).read_text(encoding="utf-8"))

    email, password = os.environ.get("EOS_SUPER_ADMIN_EMAIL"), os.environ.get("EOS_SUPER_ADMIN_PASSWORD")
    if not email or not password:
        say("set EOS_SUPER_ADMIN_EMAIL and EOS_SUPER_ADMIN_PASSWORD (the stack's .env.api values)")
        return 2

    async with client_for(a.base, 10) as client:
        health = (await client.get("/health")).json()
        if not health.get("dev_mode"):
            say(f"refusing to run: {a.base} is not in dev mode, so it may be a real site (load tests register orgs)")
            return 2
        run = secrets.token_hex(3)
        say(f"run {run} against {a.base} ({health.get('database')}), {a.orgs} organisations, stages {stages}")
        root = await sign_in(client, email, password)
        t0 = time.perf_counter()
        accounts = await seed(client, run, a.orgs, root)
        say(f"seeded {len(accounts)} organisations in {time.perf_counter() - t0:.0f} s")

    shared = [(acc.email, acc.slug, acc.token, PASSWORD) for acc in accounts]
    results: list[dict] = []
    for c in stages:
        for name in ("signin", "dashboard", "registration"):
            sample = await asyncio.to_thread(scenario, a.base, name, c, a.seconds, shared, run, a.processes)
            s = sample.summary()
            results.append(s)
            say(
                f"{name:<13} {c:>3} users  {s['requests']:>6} req  {s['rps']:>7} rps  "
                f"p50 {s['p50_ms']:>7}  p95 {s['p95_ms']:>7}  p99 {s['p99_ms']:>7} ms  "
                f"errors {s['error_rate']:.2%}  rejected {s['rejected']}"
            )

    target = int(slo["concurrency"])
    missed = []
    for s in results:
        goal = slo["scenarios"].get(s["scenario"])
        if s["concurrency"] != target or not goal:
            continue
        for key in ("p95_ms", "p99_ms", "error_rate"):
            if s[key] > goal[key]:
                missed.append(f"{s['scenario']} {key} {s[key]} > {goal[key]}")
    say(f"objectives at {target} users: " + ("all met" if not missed else "MISSED: " + "; ".join(missed)))

    if a.out:
        Path(a.out).write_text(
            json.dumps(
                {
                    "run": run,
                    "base": a.base,
                    "label": a.label,
                    "orgs": a.orgs,
                    "processes": a.processes,
                    "results": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        say(f"results written to {a.out}")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
