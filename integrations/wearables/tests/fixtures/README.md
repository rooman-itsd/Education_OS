# Fixtures

Provider payloads the tests replay. They follow each provider's documented example payloads (the shapes and field names in the
developer documentation listed in docs/prd.md, "Providers"); none was recorded from a live account, because Rooman has no
developer account approved for any of the four yet (Polar and Strava can be had at once, Garmin and Google need approval).
When an account exists, replace a file with the real recorded response and the tests keep their meaning: they assert on the
fields the adapter reads. Identifiers, names and values are invented.

`google-health/` is different in kind: the Google Health API's endpoints and response shapes are **not verified** (docs/prd.md).
Those files are the shapes the adapter assumes, written down so the first real response shows exactly what differs.
