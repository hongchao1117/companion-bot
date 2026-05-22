#!/usr/bin/env python3
"""Write the complete avatar.py file."""
import ast
from pathlib import Path

content = r'''from __future__ import annotations

import logging
import math
import re
from enum import Enum
from io import BytesIO
from typing import Awaitable, Callable

import aiofiles

from .memory import Brain

logger = logging.getLogger(__name__)

ApplyAvatar = Callable[[BytesIO], Awaitable[None]]

MAX_AVATAR_PENDING_ATTEMPTS = 5
MIN_DESCRIPTION_LEN = 20


class AvatarStyle(Enum):
    """Map description keywords to visual styles."""
    FLAME = ("flame", "fire", "candle", "warm", "luminous", "light")
    FLOWER = ("flower", "blossom", "spring", "bud", "petal", "garden")
    DREAM = ("dream", "moon", "star", "night", "mist", "soft")
    GENTLE = ("gentle", "quiet", "calm", "peaceful", "dew", "water")

    @classmethod
    def detect(cls, description: str) -> "AvatarStyle":
        desc_lower = description.lower()
        best = cls.GENTLE
        best_score = 0
        for style in cls:
            score = sum(1 for kw in style.value if kw in desc_lower)
            if score > best_score:
                best_score = score
                best = style
        return best


def _generate_avatar_pillow(description: str, size: int = 256) -> BytesIO:
    """Generate a simple avatar image using Pillow based on description."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size // 2 - 10

    style = AvatarStyle.detect(description)

    if style == AvatarStyle.FLAME:
        bg_color = (255, 120, 50, 240)
        accent_color = (255, 200, 100, 200)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)
        for i in range(6):
            angle = math.pi * 2 * i / 6 - math.pi / 2
            px = cx + int(r * 0.55 * math.cos(angle))
            py = cy + int(r * 0.55 * math.sin(angle))
            pr = r // 3
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=accent_color)
        draw.ellipse([cx - r // 3, cy - r // 3, cx + r // 3, cy + r // 3], fill=(255, 255, 200, 255))
    elif style == AvatarStyle.FLOWER:
        bg_color = (255, 180, 200, 240)
        petal_color = (255, 220, 230, 200)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)
        for i in range(8):
            angle = math.pi * 2 * i / 8
            px = cx + int(r * 0.6 * math.cos(angle))
            py = cy + int(r * 0.6 * math.sin(angle))
            pr = r // 2
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=petal_color)
        draw.ellipse([cx - r // 4, cy - r // 4, cx + r // 4, cy + r // 4], fill=(255, 240, 100, 255))
    elif style == AvatarStyle.DREAM:
        bg_color = (120, 100, 200, 240)
        star_color = (200, 180, 255, 200)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)
        for i in range(5):
            angle = math.pi * 2 * i / 5 - math.pi / 2
            px = cx + int(r * 0.5 * math.cos(angle))
            py = cy + int(r * 0.5 * math.sin(angle))
            sr = r // 4
            draw.regular_polygon((px, py, sr), 5, rotation=angle, fill=star_color)
        draw.ellipse([cx - r // 3, cy - r // 3, cx + r // 3, cy + r // 3], fill=(255, 255, 220, 255))
    else:
        bg_color = (150, 200, 220, 240)
        drop_color = (180, 230, 240, 200)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)
        for i in range(7):
            angle = math.pi * 2 * i / 7
            px = cx + int(r * 0.5 * math.cos(angle))
            py = cy + int(r * 0.5 * math.sin(angle))
            dr = r // 3
            draw.ellipse([px - dr, py - dr, px + dr, py + dr], fill=drop_color)
        draw.ellipse([cx - r // 3, cy - r // 3, cx + r // 3, cy + r // 3], fill=(255, 255, 255, 200))

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def maybe_generate_avatar(
    *,
    client: object,
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

    try:
        buf = _generate_avatar_pillow(description)
    except Exception:
        logger.exception("Pillow avatar generation failed")
        _bump_avatar_attempts(brain, meta, generation_failed=True)
        return False

    assets = brain.brain_dir / "avatar.png"
    try:
        async with aiofiles.open(assets, "wb") as f:
            await f.write(buf.getvalue())
    except Exception:
        logger.exception("Could not save avatar to disk")

    identity = brain.read_identity()
    identity = re.sub(r"(- generated: ).*", r"\1true", identity, count=1)
    if "- description:" in identity and "_not chosen" in identity:
        identity = re.sub(r"(- description: ).*", rf"\1{description}", identity, count=1)
    identity = re.sub(r"(- image_url: ).*", r"\1local:avatar.png", identity, count=1)
    brain.write_identity(identity)

    if apply_to_discord:
        try:
            buf.seek(0)
            await apply_to_discord(buf)
        except Exception:
            logger.exception("Could not apply avatar to Discord profile")

    meta = brain.read_meta()
    meta["avatar_pending"] = False
    meta["avatar_pending_attempts"] = 0
    brain.write_meta(meta)

    return True


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
        parts.append("Name: " + name.group(1).strip())
    if personality:
        parts.append("Personality: " + personality.group(1).strip()[:400])
    return ". ".join(parts)
'''

# Validate syntax
try:
    ast.parse(content)
    print("Syntax OK")
    dest = Path("src/companion/avatar.py")
    dest.write_text(content, encoding="utf-8")
    print(f"Written to {dest}")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    lines = content.split("\n")
    if e.lineno:
        for i in range(max(0, e.lineno - 3), min(len(lines), e.lineno + 2)):
            marker = ">>>" if i + 1 == e.lineno else "   "
            print(f"{marker} {i+1}: {lines[i]}")
