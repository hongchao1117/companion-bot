from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Awaitable, Callable

import aiofiles
from openai import AsyncOpenAI

from .memory import Brain
from .prompt_util import safe_format
from .prompts import AVATAR_IMAGE_PROMPT

logger = logging.getLogger(__name__)

ApplyAvatar = Callable[[BytesIO], Awaitable[None]]

MAX_AVATAR_PENDING_ATTEMPTS = 5
MIN_DESCRIPTION_LEN = 20


async def maybe_generate_avatar(
    *,
    client: AsyncOpenAI,
    brain: Brain,
    apply_to_discord: ApplyAvatar | None = None,
) -> bool:
    """Generate avatar image if pending and update identity + Discord profile."""
    meta = brain.read_meta()
    if not meta.get("avatar_pending"):
        return False

    description = meta.get("avatar_description") or _description_from_identity(brain)
    if not description or len(description) < MIN_DESCRIPTION_LEN:
        _bump_avatar_attempts(brain, meta)
        return False

    # DeepSeek doesn't support image generation — skip DALL·E,
    # just mark avatar as described in identity for future use.
    identity = brain.read_identity()

    # Update generated flag
    identity = re.sub(
        r"(- generated: ).*",
        r"\1false",
        identity,
        count=1,
    )
    # Update description if it's still placeholder
    if "- description:" in identity and "_not chosen" in identity:
        identity = re.sub(
            r"(- description: ).*",
            rf"\1{description}",
            identity,
            count=1,
        )
    brain.write_identity(identity)

    meta = brain.read_meta()
    meta["avatar_pending"] = False
    meta["avatar_pending_attempts"] = 0
    brain.write_meta(meta)

    return False


def _bump_avatar_attempts(
    brain: Brain,
    meta: dict,
    *,
    generation_failed: bool = False,
) -> None:
    attempts = int(meta.get("avatar_pending_attempts", 0)) + 1
    meta = brain.read_meta()
    meta["avatar_pending_attempts"] = attempts
    if attempts >= MAX_AVATAR_PENDING_ATTEMPTS:
        logger.warning(
            "Clearing avatar_pending after %s attempts (generation_failed=%s)",
            attempts,
            generation_failed,
        )
        meta["avatar_pending"] = False
        meta["avatar_pending_attempts"] = 0
    brain.write_meta(meta)


def _description_from_identity(brain: Brain) -> str:
    text = brain.read_identity()
    match = re.search(r"- description: (.+)", text)
    if match and "_not chosen" not in match.group(1):
        return match.group(1).strip()
    personality = re.search(r"## Personality\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
    name = re.search(r"## Name\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
    parts = []
    if name:
        parts.append(f"Name: {name.group(1).strip()}")
    if personality:
        parts.append(f"Personality: {personality.group(1).strip()[:400]}")
    return ". ".join(parts)

