"""`python -m eos_integration_hub.rotate_kek`: re-encrypt the secret store and the hub's encrypted columns under
INTEGRATION_HUB_SECRET_KEK (application/keys.py). Prints counts; exits 1 when something neither key opens."""

from __future__ import annotations

import json
import sys

from .application.keys import rotate_kek


def main() -> int:
    counts = rotate_kek()
    sys.stdout.write(json.dumps(counts, sort_keys=True) + "\n")
    return 1 if counts["unreadable"] else 0


if __name__ == "__main__":
    sys.exit(main())
