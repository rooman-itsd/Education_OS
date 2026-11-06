# Fixtures

Provider payloads the tests replay. They follow each provider's documented example payloads (the shapes and field names in
the developer documentation listed in docs/prd.md, "Sources"); none was recorded from a live account, because Rooman has no
developer account for any of the four yet. When an account exists, replace a file with the real recorded response and the
tests keep their meaning: they assert on the fields the adapter reads. Identifiers, names and addresses are invented.
