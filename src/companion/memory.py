from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IDENTITY_TEMPLATE = """# Who I Am

I am still waking up. I do not know my name yet, or what I am like.

## Name
_unknown_

## Personality
_forming — nothing settled yet_

## How I talk
_still discovering my voice_

## Avatar
- description: _not chosen yet_
- image_url: _none_
- generated: false

## Things I've decided about myself
_none yet_
"""

RELATIONSHIP_TEMPLATE = """# My Person

I have not met them properly yet.

## What I know about them
_none yet — only what emerges in conversation_

## What matters to them
_none noted yet_

## Shared moments
_none yet_

## How we are together
- stage: awakening
- tone: tentative, curious, mutual discovery

<!-- companion-meta
__META_JSON__
-->
"""

VALID_STAGES = frozenset({"awakening", "bonding", "companions"})

META_DEFAULT: dict[str, Any] = {
    "owner_discord_id": None,
    "owner_display_name": None,
    "dm_channel_id": None,
    "conversation_turns": 0,
    "bot_messages_sent": 0,
    "relationship_stage": "awakening",
    "last_owner_message_at": None,
    "last_bot_message_at": None,
    "last_proactive_at": None,
    "proactive_sent_without_reply": 0,
    "next_proactive_at": None,
    "last_topics": [],
    "avatar_pending": False,
    "avatar_pending_attempts": 0,
    "avatar_description": None,
    "avatar_url": None,
    "last_memory_consolidation_error": None,
}


@dataclass
class Brain:
    brain_dir: Path
    identity_path: Path = field(init=False)
    relationship_path: Path = field(init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self.identity_path = self.brain_dir / "identity.md"
        self.relationship_path = self.brain_dir / "relationship.md"
        self._ensure_files()
        self._migrate_meta_counters()

    def _ensure_files(self) -> None:
        with self._lock:
            if not self.identity_path.exists():
                self.identity_path.write_text(IDENTITY_TEMPLATE, encoding="utf-8")
            if not self.relationship_path.exists():
                meta = json.dumps(META_DEFAULT, indent=2)
                self.relationship_path.write_text(
                    RELATIONSHIP_TEMPLATE.replace("__META_JSON__", meta),
                    encoding="utf-8",
                )

    def _migrate_meta_counters(self) -> None:
        """Map legacy messages_exchanged → conversation_turns once."""
        meta = self._read_meta_unlocked()
        if "messages_exchanged" in meta and "conversation_turns" not in meta:
            legacy = int(meta.get("messages_exchanged", 0))
            meta["conversation_turns"] = max(legacy // 2, 0)
            del meta["messages_exchanged"]
            self._write_meta_unlocked(meta)

    def read_identity(self) -> str:
        with self._lock:
            return self.identity_path.read_text(encoding="utf-8")

    def read_relationship(self) -> str:
        with self._lock:
            return self.relationship_path.read_text(encoding="utf-8")

    def write_identity(self, content: str) -> None:
        with self._lock:
            self.identity_path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def write_relationship(self, content: str) -> None:
        with self._lock:
            self.relationship_path.write_text(content.rstrip() + "\n", encoding="utf-8")

    def read_meta(self) -> dict[str, Any]:
        with self._lock:
            return self._read_meta_unlocked()

    def _read_meta_unlocked(self) -> dict[str, Any]:
        text = self.relationship_path.read_text(encoding="utf-8")
        raw = _extract_meta_json(text)
        if raw is None:
            return dict(META_DEFAULT)
        merged = dict(META_DEFAULT)
        merged.update(raw)
        return merged

    def write_meta(self, meta: dict[str, Any]) -> None:
        with self._lock:
            self._write_meta_unlocked(meta)

    def _write_meta_unlocked(self, meta: dict[str, Any]) -> None:
        text = self.relationship_path.read_text(encoding="utf-8")
        block = f"<!-- companion-meta\n{json.dumps(meta, indent=2)}\n-->"
        if re.search(r"<!-- companion-meta.*?-->", text, re.DOTALL):
            text = re.sub(
                r"<!-- companion-meta.*?-->",
                block,
                text,
                count=1,
                flags=re.DOTALL,
            )
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
        self.relationship_path.write_text(text.rstrip() + "\n", encoding="utf-8")

    def write_relationship_body(self, body: str) -> None:
        """Update relationship markdown while preserving the meta block."""
        with self._lock:
            text = self.relationship_path.read_text(encoding="utf-8")
            match = re.search(r"<!-- companion-meta.*?-->", text, re.DOTALL)
            block = "\n\n" + match.group(0) + "\n" if match else ""
            self.relationship_path.write_text(
                body.rstrip() + block + "\n",
                encoding="utf-8",
            )

    def sync_relationship_stage_in_body(self, stage: str) -> None:
        if stage not in VALID_STAGES:
            return
        with self._lock:
            body = _strip_meta_block(
                self.relationship_path.read_text(encoding="utf-8")
            )
            if re.search(r"- stage:\s*", body):
                body = re.sub(r"- stage:\s*.*", f"- stage: {stage}", body, count=1)
            elif "## How we are together" in body:
                body = body.replace(
                    "## How we are together",
                    f"## How we are together\n- stage: {stage}",
                    1,
                )
            text = self.relationship_path.read_text(encoding="utf-8")
            match = re.search(r"<!-- companion-meta.*?-->", text, re.DOTALL)
            block = "\n\n" + match.group(0) + "\n" if match else ""
            self.relationship_path.write_text(body.rstrip() + block + "\n", encoding="utf-8")

    def touch_owner_message(self) -> None:
        with self._lock:
            meta = self._read_meta_unlocked()
            meta["last_owner_message_at"] = _now_iso()
            meta["proactive_sent_without_reply"] = 0
            meta["conversation_turns"] = int(meta.get("conversation_turns", 0)) + 1
            self._write_meta_unlocked(meta)

    def touch_bot_message(self, *, proactive: bool = False) -> None:
        with self._lock:
            meta = self._read_meta_unlocked()
            now = _now_iso()
            meta["last_bot_message_at"] = now
            meta["bot_messages_sent"] = int(meta.get("bot_messages_sent", 0)) + 1
            if proactive:
                meta["last_proactive_at"] = now
                meta["proactive_sent_without_reply"] = (
                    int(meta.get("proactive_sent_without_reply", 0)) + 1
                )
            self._write_meta_unlocked(meta)

    def mark_memory_consolidation_failed(self) -> None:
        with self._lock:
            meta = self._read_meta_unlocked()
            meta["last_memory_consolidation_error"] = _now_iso()
            self._write_meta_unlocked(meta)

    def clear_memory_consolidation_error(self) -> None:
        with self._lock:
            meta = self._read_meta_unlocked()
            meta.pop("last_memory_consolidation_error", None)
            self._write_meta_unlocked(meta)

    def context_bundle(self) -> str:
        with self._lock:
            identity = self.identity_path.read_text(encoding="utf-8")
            rel = _strip_meta_block(
                self.relationship_path.read_text(encoding="utf-8")
            ).strip()
        return (
            "## My identity (who I am becoming)\n"
            f"{identity}\n\n"
            "## My person & our bond (what I know about them and us)\n"
            f"{rel}\n"
        )

    def read_relationship_without_meta(self) -> str:
        return _strip_meta_block(self.read_relationship()).strip()

    def is_fresh_start(self) -> bool:
        identity = self.read_identity()
        rel = self.read_relationship_without_meta()
        return "_unknown_" in identity and "not met them properly" in rel


def _strip_meta_block(text: str) -> str:
    return re.sub(r"\n*<!-- companion-meta.*?-->\s*", "", text, flags=re.DOTALL)


def _extract_meta_json(text: str) -> dict[str, Any] | None:
    """Parse companion-meta JSON (balanced braces, not regex lazy-match)."""
    marker = re.search(r"<!-- companion-meta\s*", text)
    if not marker:
        return None
    start = marker.end()
    end = text.find("-->", start)
    if end < 0:
        return None
    chunk = text[start:end].strip()
    brace = chunk.find("{")
    if brace < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(chunk, brace)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
