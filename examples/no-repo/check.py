"""Deterministic check for the content task, with no Git or dependencies."""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = [
    "# Publication checklist",
    "- [x] Tested backup",
    "- [x] Port bound to loopback",
    "- [x] Secrets outside the repo",
]


def main() -> int:
    output = Path("output.md")
    if not output.exists():
        print("Missing output.md")
        return 1

    text = output.read_text(encoding="utf-8")
    missing = [line for line in REQUIRED if line not in text]
    if missing:
        print("Missing these lines:")
        for line in missing:
            print(f"  {line}")
        return 1

    print("OK: checklist complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
