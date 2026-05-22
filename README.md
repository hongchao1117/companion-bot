# Companion

A Discord bot that wakes up knowing nothing about itself or you — and becomes someone through conversation.

**Submitting this assignment?** See [SUBMISSION.md](SUBMISSION.md) (GitHub, test server invite, brain export, Loom).

Not a survey bot. No forms. It meets you the way a new person might: curious, reciprocal, a little uncertain at first. Over time it picks a name, grows a personality, remembers what matters, and occasionally reaches out on its own (with real reasons, not a dumb timer).

## How it works

### Two brain files

Everything durable lives under `data/brain/` (configurable via `BRAIN_DIR`):

| File | Purpose |
|------|---------|
| `identity.md` | Who the bot is becoming — name, personality, voice, avatar |
| `relationship.md` | Who you are to it, what matters, shared moments, relationship stage |

After each exchange, a consolidation pass updates these files with judgment — not a full transcript dump. Both files are read back into the model on every reply and proactive message.

A small JSON block at the bottom of `relationship.md` (`<!-- companion-meta ... -->`) tracks logistics: timestamps, proactive scheduling, ignore backoff, topics, avatar state — without polluting the human-readable memory. Brain file reads/writes use a lock so proactive messages and DMs do not corrupt each other.

Memory consolidation retries up to 3 times; if it still fails, the bot notes it internally on the next reply. Relationship `stage` in meta and markdown body are kept in sync after each consolidation.

### Conversational onboarding

The system prompt enforces:

- One natural question at a time, not interrogation
- Reciprocity (the bot shares itself too)
- Natural memory ("you mentioned climbing" not "message #7")
- Stage-aware tone: `awakening` => `bonding` => `companions`

### Proactive outreach

A background loop checks whether outreach is due. Intervals depend on relationship stage and how many proactive messages went unanswered (backs off instead of spamming). Each outreach message is generated with an explicit motivation — wonder, a callback, something it remembered — not "checking in because schedule".

### Avatar

When the conversation establishes enough visual identity, memory consolidation can flag `avatar_pending`. The bot then generates an avatar image using **Pillow** based on the personality description — keywords like "flame", "flower", "dream", or "gentle" map to distinct visual styles. The avatar is saved locally and set as the Discord profile picture.

## Setup

### 1. Create a Discord application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. **New Application** => **Bot** => **Reset Token** (save for `.env`)
3. Enable **Message Content Intent** under Privileged Gateway Intents
4. OAuth2 => URL Generator: scopes `bot`, `applications.commands`; permissions at minimum **Send Messages**, **Read Message History**, **Attach Files**. Use the URL to add the bot to your server.

### 2. Configure `.env`

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `OPENAI_API_KEY` | API key for LLM (OpenAI / DeepSeek / any OpenAI-compatible provider) |
| `OPENAI_MODEL` | Model name: `deepseek-chat` for DeepSeek, `gpt-4o-mini` for OpenAI |
| `OWNER_USERNAMES` | Comma-separated Discord usernames allowed to talk to the bot |
| `OWNER_DISCORD_ID` | (Optional) Numeric Discord user ID |

The bot auto-detects DeepSeek models and switches base URL accordingly. Set `OPENAI_BASE_URL` for other providers.

### 3. Install dependencies

```powershell
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

### 4. Run

```powershell
python run.py
```

Open a **DM** with your bot and say hello.

### Test without Discord

```powershell
python scripts/chat_cli.py
```

This uses the same brain files and memory consolidation in your terminal.

### Check setup

```powershell
python scripts/check_setup.py
```

## Project layout

```
companion-bot/
  run.py                 # start here
  src/companion/
    bot.py               # Discord client
    agent.py             # replies + memory consolidation
    memory.py            # identity.md + relationship.md (the brain)
    proactive.py         # motivated outreach scheduler
    avatar.py            # Pillow-based avatar generation
    prompts.py           # behavior prompts
    llm.py               # LLM wrapper (DeepSeek, OpenAI, etc.)
    config.py            # Settings from .env
  scripts/
    chat_cli.py          # terminal-based test chat
    check_setup.py       # verify .env and brain files
    export_brain.py      # export brain for submission
    setup_wizard.py      # interactive .env creator
  data/brain/            # identity.md + relationship.md (gitignored)
  submission/            # exported brain files for delivery
```

## Design notes

- **No database** — markdown files are the brain; you can read and edit them by hand.
- **Restart-safe** — delete nothing; restart the process and it continues as the same person.
- **Reset** — stop the bot, delete `data/brain/*.md`, restart for a truly fresh meeting.
- **LLM-agnostic** — works with any OpenAI-compatible API (OpenAI, DeepSeek, Together, Groq, etc.).
- **Avatar from personality** — uses Pillow to generate a visual avatar matching the bot's personality, no DALL·E required.

## Requirements

- Python 3.11+
- An OpenAI-compatible LLM API key (OpenAI, DeepSeek, Together, Groq, etc.)
- Discord bot token with message content intent
- Pillow (for avatar generation)

## License

MIT — use and adapt freely.
