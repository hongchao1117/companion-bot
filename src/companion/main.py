from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running as `python -m companion.main` from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from companion.bot import CompanionBot
from companion.config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    bot = CompanionBot(settings)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
