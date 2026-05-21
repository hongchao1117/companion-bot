#!/usr/bin/env python3
"""Local chat without Discord — tests brain + memory when API key is set.

    python scripts/chat_cli.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from companion.agent import CompanionAgent
from companion.config import Settings
from companion.llm import LLM
from companion.memory import Brain


async def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key.startswith("sk-"):
        print("Set OPENAI_API_KEY in .env first (Discord token not required for CLI).")
        print("  python scripts/setup_wizard.py")
        raise SystemExit(1)

    brain_dir = Path(os.getenv("BRAIN_DIR", "./data/brain"))
    if not brain_dir.is_absolute():
        brain_dir = (ROOT / brain_dir).resolve()

    brain = Brain(brain_dir)
    llm = LLM(api_key, os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    agent = CompanionAgent(llm, brain)

    print("Companion CLI (type 'quit' to exit)\n")
    name = os.getenv("CLI_USER_NAME", "You")
    while True:
        try:
            line = input(f"{name}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            break
        reply = await agent.reply(user_name=name, user_message=line)
        print(f"\nCompanion: {reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
