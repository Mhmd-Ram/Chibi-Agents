from __future__ import annotations

import sys

# Load .env BEFORE importing app — the AISpeechProvider reads ANTHROPIC_API_KEY
# at construction time.
from .env_loader import autoload as _autoload_dotenv  # noqa: E402

_autoload_dotenv()

from .app import run  # noqa: E402


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
