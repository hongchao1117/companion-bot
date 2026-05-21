from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable, Awaitable

from .llm import LLM, validate_proactive_response
from .memory import Brain
from .prompt_util import safe_format
from .prompts import PROACTIVE_PROMPT

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

SendFn = Callable[[str], Awaitable[None]]

# Base intervals (hours) by stage — scaled up when ignored
BASE_INTERVAL_HOURS = {
    "awakening": 8,
    "bonding": 18,
    "companions": 36,
}

MAX_IGNORED_BACKOFF = 4


class ProactiveScheduler:
    def __init__(
        self,
        *,
        brain: Brain,
        llm: LLM,
        send: SendFn,
        owner_hour_hint: Callable[[], int] | None = None,
    ) -> None:
        self.brain = brain
        self.llm = llm
        self.send = send
        self.owner_hour_hint = owner_hour_hint or (lambda: datetime.now().hour)
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        await asyncio.sleep(30)
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Proactive tick failed")
            await asyncio.sleep(60)

    async def _tick(self) -> None:
        meta = self.brain.read_meta()
        if not meta.get("dm_channel_id"):
            return

        now = datetime.now(timezone.utc)
        next_at = meta.get("next_proactive_at")
        if next_at:
            due = datetime.fromisoformat(next_at.replace("Z", "+00:00"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if now < due:
                return

        hours_since = _hours_since(meta.get("last_owner_message_at"))
        ignored = int(meta.get("proactive_sent_without_reply", 0))
        if ignored >= MAX_IGNORED_BACKOFF and hours_since < 24:
            self._schedule_next(hours=24)
            return

        stage = str(meta.get("relationship_stage", "awakening"))
        message = await self._craft_message(stage=stage, hours_since=hours_since, ignored=ignored)
        if not message:
            self._schedule_next(hours=12)
            return

        await self.send(message)
        self.brain.touch_bot_message(proactive=True)
        interval = self._next_interval_hours(stage, ignored)
        self._schedule_next(hours=interval)

    async def _craft_message(
        self, *, stage: str, hours_since: float | None, ignored: int
    ) -> str | None:
        meta = self.brain.read_meta()
        topics = ", ".join(meta.get("last_topics") or []) or "nothing specific yet"
        prompt = safe_format(
            PROACTIVE_PROMPT,
            brain=self.brain.context_bundle(),
            stage=stage,
            hours_since_owner=str(
                round(hours_since, 1) if hours_since is not None else "unknown"
            ),
            ignored_count=str(ignored),
            topics=topics,
            time_hint=f"around {self.owner_hour_hint()}:00 local (approximate)",
        )
        try:
            data = await self.llm.complete_json_with_retry(
                system="You write proactive outreach for a companion bot.",
                user=prompt,
                validator=validate_proactive_response,
                temperature=0.88,
                max_tokens=500,
                max_attempts=3,
            )
            return (data.get("message") or "").strip() or None
        except Exception:
            logger.exception("Proactive message generation failed")
            return None

    def _next_interval_hours(self, stage: str, ignored: int) -> float:
        base = BASE_INTERVAL_HOURS.get(stage, 18)
        multiplier = 1.0 + (ignored * 0.75)
        return min(base * multiplier, 72)

    def _schedule_next(self, *, hours: float) -> None:
        meta = self.brain.read_meta()
        due = datetime.now(timezone.utc) + timedelta(hours=hours)
        meta["next_proactive_at"] = due.isoformat()
        self.brain.write_meta(meta)

    def on_owner_replied(self) -> None:
        """Reschedule proactive outreach after owner replies (ignore count reset in touch_owner_message)."""
        meta = self.brain.read_meta()
        stage = str(meta.get("relationship_stage", "awakening"))
        self._schedule_next(hours=self._next_interval_hours(stage, 0) * 0.5)


def _hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - then
        return delta.total_seconds() / 3600
    except ValueError:
        return None
