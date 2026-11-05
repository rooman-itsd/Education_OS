# wearables

Athletes' own device data. Implements the **wearable-data** port defined by `platform/integration-hub`
([`contracts/ports/wearable-data.yaml`](contracts/ports/wearable-data.yaml)) for Garmin, Polar, Fitbit (through the
Google Health API) and Strava: an athlete links their own account, the adapter receives daily summaries, sleep and
workouts as the provider makes them available, normalises them to one shape and units, and athlete-performance and
sports-nutrition-health read them for that athlete. Nothing flows without the athlete's own authorisation, and
disconnecting deletes what was collected.

**Status:** contracts proposed (0.2.0); not built. See [docs/prd.md](docs/prd.md).

- `contracts/ports/` — the port and the Adapter contract, copied from integration-hub
- `contracts/openapi.yaml` — provider callbacks (received by integration-hub) and the coach's alerts (`wearables.alerts`)
- `src/` — one provider client per device maker, and the normaliser
- `config/env.example` — Rooman's developer apps per provider
- `tests/` — contract tests against recorded fixtures, and each provider's developer access when configured
