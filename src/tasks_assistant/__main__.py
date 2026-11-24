"""Allow running the CLI with ``python -m tasks_assistant``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
