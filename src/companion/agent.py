from __future__ import annotations

import logging
from typing import Any

from .llm import LLM, validate_memory_consolidation
from .memory import Brain, VALID_STAGES
from .prompt_util import safe_format
from .prompts import MEMORY_EXTRACTION_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

CONSOLIDATION_RETRIES = 3


class CompanionAgent:
    def __init__(self, llm: LLM, brain: Brain) -> None:
        self.llm = llm
        self.brain = brain
        self._recent_turns: list[tuple[str, str]] = []

    def _stage(self) -> str:
        return str(self.brain.read_meta().get("relationship_stage", "awakening"))

    def _memory_note(self) -> str:
        if self.brain.read_meta().get("last_memory_consolidation_error"):
            return (
                "(Internal note: your last memory save failed — rely on the brain files "
                "above; this message may not be fully reflected in them yet.)"
            )
        return ""

    def _format_recent_exchange(self) -> str:
        if not self._recent_turns:
            return "_first message this session_"
        lines: list[str] = []
        for user, bot in self._recent_turns[-4:]:
            lines.append(f"Them: {user}")
            lines.append(f"You: {bot}")
        return "\n".join(lines)

    async def reply(self, *, user_name: str, user_message: str) -> str:
        system = safe_format(
            SYSTEM_PROMPT,
            brain=self.brain.context_bundle(),
            stage=self._stage(),
            recent_exchange=self._format_recent_exchange(),
            memory_note=self._memory_note(),
            user_name=user_name,
            user_message=user_message,
        )
        reply = await self.llm.complete(
            system=system,
            user="Respond as the companion.",
            temperature=0.9,
        )
        self._recent_turns.append((user_message, reply))
        if len(self._recent_turns) > 6:
            self._recent_turns = self._recent_turns[-6:]
        await self._consolidate_memory(
            user_name=user_name,
            user_message=user_message,
            bot_reply=reply,
        )
        return reply

    async def _consolidate_memory(
        self,
        *,
        user_name: str,
        user_message: str,
        bot_reply: str,
    ) -> None:
        prompt = safe_format(
            MEMORY_EXTRACTION_PROMPT,
            identity=self.brain.read_identity(),
            relationship=self.brain.read_relationship_without_meta(),
            user_name=user_name,
            user_message=user_message,
            bot_reply=bot_reply,
        )
        try:
            data = await self.llm.complete_json_with_retry(
                system="You update markdown memory files for a companion AI.",
                user=prompt,
                validator=validate_memory_consolidation,
                temperature=0.35,
                max_tokens=3000,
                max_attempts=CONSOLIDATION_RETRIES,
            )
        except Exception:
            logger.exception("Memory consolidation failed after retries")
            self.brain.mark_memory_consolidation_failed()
            return

        self.brain.clear_memory_consolidation_error()
        self._apply_consolidation(data)

    def _apply_consolidation(self, data: dict[str, Any]) -> None:
        identity_md = data.get("identity_md")
        relationship_md = data.get("relationship_md")
        if identity_md:
            self.brain.write_identity(identity_md)
        if relationship_md:
            self.brain.write_relationship_body(
                _strip_meta_from_llm_output(relationship_md)
            )

        meta_updates = data.get("meta_updates") or {}
        meta = self.brain.read_meta()
        stage = meta_updates.get("relationship_stage")
        if stage in VALID_STAGES:
            meta["relationship_stage"] = stage
        for key in ("owner_display_name",):
            if meta_updates.get(key):
                meta[key] = meta_updates[key]
        topics = meta_updates.get("last_topics")
        if topics:
            merged = list(meta.get("last_topics") or [])
            for t in topics:
                if t and t not in merged:
                    merged.append(t)
            meta["last_topics"] = merged[-8:]
        if meta_updates.get("avatar_description"):
            meta["avatar_description"] = meta_updates["avatar_description"]
            meta["avatar_pending_attempts"] = 0

        if data.get("should_generate_avatar") or meta_updates.get("avatar_ready"):
            meta["avatar_pending"] = True
            meta["avatar_pending_attempts"] = 0

        self.brain.write_meta(meta)

        stage = str(meta.get("relationship_stage", "awakening"))
        self.brain.sync_relationship_stage_in_body(stage)

    def _attach_meta(self, relationship_md: str, _data: dict[str, Any]) -> str:
        """Deprecated: use write_relationship_body; kept for tests."""
        return _strip_meta_from_llm_output(relationship_md)


def _strip_meta_from_llm_output(relationship_md: str) -> str:
    import re

    return re.sub(
        r"\n*<!-- companion-meta.*?-->\s*",
        "",
        relationship_md,
        flags=re.DOTALL,
    ).strip()
