from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from openai import AsyncOpenAI

from .agent import CompanionAgent
from .avatar import maybe_generate_avatar
from .config import Settings
from .llm import LLM
from .memory import Brain
from .proactive import ProactiveScheduler

logger = logging.getLogger(__name__)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.dm_messages = True
INTENTS.guilds = True


class CompanionBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        super().__init__(intents=INTENTS)
        self.settings = settings
        self.brain = Brain(settings.brain_dir)
        self.llm = LLM(settings.openai_api_key, settings.openai_model)
        self.agent = CompanionAgent(self.llm, self.brain)
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._scheduler: ProactiveScheduler | None = None

    async def setup_hook(self) -> None:
        self._scheduler = ProactiveScheduler(
            brain=self.brain,
            llm=self.llm,
            send=self._send_proactive,
        )
        self._scheduler.start()

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user and self.user.id)
        meta = self.brain.read_meta()
        if meta.get("dm_channel_id"):
            logger.info("Reply channel %s", meta["dm_channel_id"])
        if self.settings.test_channel_id:
            logger.info(
                "Test channel enabled: %s (guild %s)",
                self.settings.test_channel_id,
                self.settings.test_guild_id,
            )
        allowed = list(self.settings.owner_discord_ids)
        if self.settings.owner_usernames:
            allowed.append(f"usernames:{','.join(self.settings.owner_usernames)}")
        logger.info("Allowed owners: %s", allowed)
        if self.brain.is_fresh_start():
            logger.info("Fresh brain — meeting someone new")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return

        if not self.settings.is_allowed_owner(message.author):
            return

        if not self._is_chat_channel(message.channel):
            if message.guild:
                hint = (
                    "I can talk in DMs"
                    + (
                        f" or in <#{self.settings.test_channel_id}> for testing."
                        if self.settings.test_channel_id
                        else "."
                    )
                )
                await message.channel.send(hint)
            return

        await self._register_contact(message)
        self.brain.touch_owner_message()
        if self._scheduler:
            self._scheduler.on_owner_replied()

        try:
            async with message.channel.typing():
                reply = await self.agent.reply(
                    user_name=message.author.display_name,
                    user_message=message.content.strip(),
                )
        except Exception:
            logger.exception("Failed to generate reply")
            await message.channel.send(
                "Something went wrong on my end — give me a moment and try again?"
            )
            return

        chunks = _split_message(reply)
        if not chunks:
            await message.channel.send("…")
            chunks = ["…"]

        for chunk in chunks:
            await message.channel.send(chunk)

        self.brain.touch_bot_message(proactive=False)
        await self._maybe_avatar()

    def _is_chat_channel(self, channel: discord.abc.MessageableChannel) -> bool:
        if isinstance(channel, discord.DMChannel):
            return True
        if self.settings.is_test_channel(channel):
            if self.settings.test_guild_id and isinstance(channel, discord.TextChannel):
                return channel.guild.id == self.settings.test_guild_id
            return True
        return False

    async def _register_contact(self, message: discord.Message) -> None:
        meta = self.brain.read_meta()
        changed = False
        author = message.author
        if not meta.get("owner_discord_id"):
            meta["owner_discord_id"] = author.id
            changed = True
        if not meta.get("dm_channel_id"):
            meta["dm_channel_id"] = message.channel.id
            changed = True
        if not meta.get("owner_display_name"):
            meta["owner_display_name"] = getattr(author, "display_name", author.name)
            changed = True
        owners = list(meta.get("allowed_owner_ids") or [])
        if author.id not in owners:
            owners.append(author.id)
            meta["allowed_owner_ids"] = owners
            changed = True
        if not meta.get("next_proactive_at"):
            meta["next_proactive_at"] = (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat()
            changed = True
        if changed:
            self.brain.write_meta(meta)

    async def _send_proactive(self, text: str) -> None:
        meta = self.brain.read_meta()
        channel_id = meta.get("dm_channel_id")
        if not channel_id:
            return
        channel = self.get_channel(int(channel_id))
        if channel is None:
            channel = await self.fetch_channel(int(channel_id))
        if channel is None:
            return
        for chunk in _split_message(text):
            await channel.send(chunk)
        await self._maybe_avatar()

    async def _maybe_avatar(self) -> None:
        from io import BytesIO

        async def apply_from_bytesIO(bio: BytesIO) -> None:
            if self.user:
                bio.seek(0)
                await self.user.edit(avatar=bio.read())

        await maybe_generate_avatar(
            client=self._openai,
            brain=self.brain,
            apply_to_discord=apply_from_bytesIO,
        )

    async def close(self) -> None:
        if self._scheduler:
            self._scheduler.stop()
        await super().close()


def _split_message(text: str, limit: int = 1900) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split = text.rfind("\n", 0, limit)
        if split < limit // 2:
            split = limit
        chunks.append(text[:split].strip())
        text = text[split:].strip()
    return chunks
