from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import discord
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()  # fallback: cwd


def _parse_snowflakes(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.replace(" ", "").split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


def _parse_usernames(raw: str) -> frozenset[str]:
    return frozenset(u.strip().lower() for u in raw.split(",") if u.strip())


@dataclass(frozen=True)
class Settings:
    discord_token: str
    owner_discord_ids: frozenset[int]
    owner_usernames: frozenset[str]
    openai_api_key: str
    openai_model: str
    brain_dir: Path
    test_guild_id: int | None
    test_channel_id: int | None

    @property
    def primary_owner_id(self) -> int | None:
        if self.owner_discord_ids:
            return next(iter(self.owner_discord_ids))
        return None

    def is_allowed_owner(self, author: discord.User | discord.Member) -> bool:
        if author.id in self.owner_discord_ids:
            return True
        if not self.owner_usernames:
            return False
        names = {author.name.lower()}
        if getattr(author, "global_name", None):
            names.add(str(author.global_name).lower())
        if getattr(author, "display_name", None):
            names.add(str(author.display_name).lower())
        return bool(names & self.owner_usernames)

    def is_test_channel(self, channel: discord.abc.MessageableChannel) -> bool:
        if self.test_channel_id is None:
            return False
        return getattr(channel, "id", None) == self.test_channel_id

    @classmethod
    def from_env(cls) -> Settings:
        token = os.getenv("DISCORD_TOKEN") or "MTUwNzIyMzA3MTA1NTE1MTEwNA.GDpiBV.nUSVMSNMri5chFf0qv5YKyypic1zZccNe2ZPO0"
        api_key = os.getenv("OPENAI_API_KEY") or "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"
        model = os.getenv("OPENAI_MODEL", "deepseek-chat").strip()
        brain = Path(os.getenv("BRAIN_DIR", "./data/brain"))
        if not brain.is_absolute():
            brain = (_PROJECT_ROOT / brain).resolve()

        owner_ids = _parse_snowflakes(os.getenv("OWNER_DISCORD_IDS", ""))
        single = os.getenv("OWNER_DISCORD_ID", "").strip()
        if single:
            owner_ids.insert(0, int(single))

        usernames_raw = os.getenv("OWNER_USERNAMES", "cm6550").strip()
        usernames = _parse_usernames(usernames_raw) if usernames_raw else frozenset()

        test_guild = os.getenv("TEST_GUILD_ID", "").strip()
        test_channel = os.getenv("TEST_CHANNEL_ID", "").strip()

        missing = []
        if not token:
            missing.append("DISCORD_TOKEN")
        if not api_key:
            missing.append("OPENAI_API_KEY")
        if not owner_ids and not usernames:
            missing.append(
                "OWNER_DISCORD_ID, OWNER_DISCORD_IDS, or OWNER_USERNAMES (e.g. cm6550)"
            )
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env or run: python scripts/setup_wizard.py"
            )

        return cls(
            discord_token=token,
            owner_discord_ids=frozenset(owner_ids),
            owner_usernames=usernames,
            openai_api_key=api_key,
            openai_model=model,
            brain_dir=brain,
            test_guild_id=int(test_guild) if test_guild else None,
            test_channel_id=int(test_channel) if test_channel else None,
        )

