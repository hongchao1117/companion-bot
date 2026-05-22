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
- Stage-aware tone: `awakening` → `bonding` → `companions`

### Proactive outreach

A background loop checks whether outreach is due. Intervals depend on relationship stage and how many proactive messages went unanswered (backs off instead of spamming). Each outreach message is generated with an explicit motivation — wonder, a callback, something it remembered — not "checking in because schedule."

### Avatar

When the conversation establishes enough visual identity, memory consolidation can flag `avatar_pending`. The bot then uses Pillow, saves the file into `identity.md`, and optionally sets the Discord profile picture.

## Setup

### 1. Create a Discord application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. **New Application** → **Bot** → **Reset Token** (save for `.env`)
3. Enable **Message Content Intent** under Privileged Gateway Intents
4. OAuth2 → URL Generator: scopes `bot`, `applications.commands`; permissions at minimum **Send Messages**, **Read Message History**, **Attach Files** (for avatars). Use the URL to add the bot to your server (optional; DMs are the main channel).

### 2. Get your Discord user ID

Settings → Advanced → **Developer Mode** → right-click your profile → **Copy User ID**

### 3. One-command setup (recommended)

```powershell
cd companion-bot
.\scripts\start.ps1
```

First time, if `.env` is empty, the script will tell you to run the wizard:

```powershell
.\.venv\Scripts\python scripts\setup_wizard.py
```

Or configure manually: copy `.env.example` to `.env` and fill in `DISCORD_TOKEN`, `OWNER_DISCORD_ID`, `DeepSeek_API_KEY`.

### 4. Check setup (optional)

Verify `.env` and brain files without starting Discord:

```powershell
python scripts/check_setup.py
```

This prints masked tokens, whether required variables are set, and a snapshot of `identity.md` / `relationship.md`.

### 5. Run

```powershell
python run.py
# or: .\scripts\start.ps1
```

Open a **DM** with your bot and say hello. It only talks to `OWNER_DISCORD_ID` in DMs.

### Test without Discord (optional)

If you only have an DeepSeek key:

```powershell
.\.venv\Scripts\python scripts\chat_cli.py
```

This uses the same brain files and memory consolidation in your terminal.

## Project layout

```
companion-bot/
  run.py                 # start here
  src/companion/
    bot.py               # Discord client
    agent.py             # replies + memory consolidation
    memory.py            # identity.md + relationship.md
    proactive.py         # motivated outreach scheduler
    avatar.py            # optional Pillow avatar
    prompts.py           # behavior prompts
  data/brain/            # created at runtime (gitignored)
```

## Design notes

- **No database** — markdown files are the brain; you can read and edit them by hand.
- **Restart-safe** — delete nothing; restart the process and it continues as the same person.
- **Reset** — stop the bot, delete `data/brain/*.md`, restart for a truly fresh meeting.

## Requirements

- Python 3.11+
- DeepSeek API access (chat + JSON memory passes; Pillow for avatars)
- Discord bot token with message content intent

## License

MIT — use and adapt freely.
