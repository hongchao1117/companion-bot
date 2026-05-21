#!/usr/bin/env python3
"""Check .env and brain files without starting Discord.

Usage (from project root):
    python scripts/check_setup.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

from companion.config import Settings
from companion.memory import Brain, META_DEFAULT

load_dotenv(ROOT / ".env")


def _mask(value: str, *, show: int = 4) -> str:
    value = value.strip()
    if not value:
        return "(empty)"
    if len(value) <= show + 2:
        return "*" * len(value)
    return value[:show] + "…" + "*" * min(8, max(0, len(value) - show - 1))


def check_env() -> list[str]:
    issues: list[str] = []
    env_path = ROOT / ".env"

    print("=== Environment (.env) ===\n")
    if not env_path.exists():
        print(f"  .env file: MISSING ({env_path})")
        issues.append("missing .env")
        return issues

    print(f"  .env file: found\n")

    token = os.getenv("DISCORD_TOKEN", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    print(f"  DISCORD_TOKEN: {_mask(token) if token else '(empty)'}  [{'OK' if token else 'MISSING'}]")
    print(f"  OPENAI_API_KEY: {_mask(api_key) if api_key else '(empty)'}  [{'OK' if api_key else 'MISSING'}]")

    if not token:
        issues.append("missing DISCORD_TOKEN")
    if not api_key:
        issues.append("missing OPENAI_API_KEY")

    usernames = os.getenv("OWNER_USERNAMES", "").strip()
    owner_id = os.getenv("OWNER_DISCORD_ID", "").strip()
    owner_ids = os.getenv("OWNER_DISCORD_IDS", "").strip()
    print(f"  OWNER_USERNAMES: {usernames or '(empty)'}")
    print(f"  OWNER_DISCORD_ID: {owner_id or '(empty)'}")
    print(f"  OWNER_DISCORD_IDS: {owner_ids or '(empty)'}")

    if not usernames and not owner_id and not owner_ids:
        issues.append("no owner configured (USERNAMES or DISCORD_ID)")
    elif usernames or owner_id or owner_ids:
        print("  Owners: OK")

    test_ch = os.getenv("TEST_CHANNEL_ID", "").strip()
    test_guild = os.getenv("TEST_GUILD_ID", "").strip()
    if test_ch:
        print(f"  TEST_CHANNEL_ID: {test_ch}  [server test enabled]")
    else:
        print("  TEST_CHANNEL_ID: (empty)  [DM-only until set]")

    if not issues:
        try:
            settings = Settings.from_env()
            print(f"\n  Parsed allowed IDs: {sorted(settings.owner_discord_ids)}")
            print(f"  Parsed allowed usernames: {sorted(settings.owner_usernames)}")
        except RuntimeError as e:
            issues.append(str(e))

    print()
    return issues


def check_brain(brain_dir: Path) -> list[str]:
    issues: list[str] = []
    print("=== Brain files ===\n")
    print(f"  BRAIN_DIR: {brain_dir.resolve()}\n")

    brain = Brain(brain_dir)
    for label, path in [
        ("identity.md", brain.identity_path),
        ("relationship.md", brain.relationship_path),
    ]:
        print(f"  {label}: {'exists' if path.exists() else 'MISSING'}")

    identity = brain.read_identity()
    rel_body = brain.read_relationship_without_meta()
    meta = brain.read_meta()

    print(f"\n  Fresh start: {brain.is_fresh_start()}")
    print(f"  Stage: {meta.get('relationship_stage')}")
    print(f"  Conversation turns: {meta.get('conversation_turns', 0)}")
    print(f"  Reply channel: {meta.get('dm_channel_id') or 'not registered yet'}")

    if meta.get("last_memory_consolidation_error"):
        print(f"  WARNING: last memory error at {meta['last_memory_consolidation_error']}")

    for section in ("## Name", "## Personality", "## Avatar"):
        if section not in identity:
            issues.append(f"identity.md missing {section}")

    print()
    return issues


def main() -> int:
    print(f"\nCompanion setup check\n{'=' * 40}\n")
    issues = check_env()
    brain_dir = Path(os.getenv("BRAIN_DIR", "./data/brain"))
    if not brain_dir.is_absolute():
        brain_dir = (ROOT / brain_dir).resolve()
    issues.extend(check_brain(brain_dir))

    print("=== Summary ===\n")
    if not issues:
        print("  All checks passed.")
        print("  Run: .\\scripts\\start.ps1")
        print("  Submit: see SUBMISSION.md\n")
        return 0

    for item in issues:
        print(f"  - {item}")
    print("\n  Run: python scripts/setup_wizard.py\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
