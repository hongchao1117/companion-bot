from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
        else:
            raise
    if not isinstance(parsed, dict):
        raise ValueError("JSON root must be an object")
    return parsed


def validate_memory_consolidation(data: dict[str, Any]) -> bool:
    """Ensure consolidation response has usable markdown updates."""
    identity = data.get("identity_md")
    relationship = data.get("relationship_md")
    has_identity = isinstance(identity, str) and len(identity.strip()) >= 20
    has_relationship = isinstance(relationship, str) and len(relationship.strip()) >= 20
    if not (has_identity or has_relationship):
        return False
    meta_updates = data.get("meta_updates")
    if meta_updates is not None and not isinstance(meta_updates, dict):
        return False
    stage = (meta_updates or {}).get("relationship_stage")
    if stage is not None and stage not in ("awakening", "bonding", "companions"):
        return False
    return True


def validate_proactive_response(data: dict[str, Any]) -> bool:
    message = data.get("message")
    return isinstance(message, str) and len(message.strip()) >= 1


class LLM:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.85,
        max_tokens: int = 700,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.5,
        max_tokens: int = 2500,
    ) -> dict[str, Any]:
        raw = await self.complete(
            system=system + "\n\nYou must respond with valid JSON only.",
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _extract_json(raw)

    async def complete_json_with_retry(
        self,
        *,
        system: str,
        user: str,
        validator: Any,
        temperature: float = 0.5,
        max_tokens: int = 2500,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                data = await self.complete_json(
                    system=system,
                    user=user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if validator(data):
                    return data
                raise ValueError("Response failed validation")
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "JSON completion attempt %s/%s failed: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(0.8 * attempt)
        assert last_error is not None
        raise last_error
