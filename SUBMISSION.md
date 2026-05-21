# Submission checklist (Companion assignment)

Use this when handing off to **pikarecruit** / reviewers.

## 1. GitHub repository

```powershell
git init
git add .
git commit -m "Companion Discord bot: persistent brain, proactive outreach"
```

Create a repo on GitHub (public or private), push, then add collaborator **pikarecruit**:
Settings → Collaborators → Add people.

## 2. Working Discord bot + test server

### A. Developer Portal

1. [Discord Developer Portal](https://discord.com/developers/applications) → your app → **Bot**
2. Enable **Message Content Intent**
3. Copy **Bot Token** → `.env` as `DISCORD_TOKEN`
4. **OAuth2 → URL Generator**
   - Scopes: `bot`
   - Permissions: Send Messages, Read Message History, View Channels
5. Copy the generated URL — this is your **server invite link** for reviewers
6. Open the URL, add the bot to your **test server**
7. Create a channel (e.g. `#companion-test`) → right-click → **Copy Channel ID** → `TEST_CHANNEL_ID`
8. Right-click server name → **Copy Server ID** → `TEST_GUILD_ID`

### B. Owners

- **`OWNER_USERNAMES=cm6550`** — reviewer can talk without you looking up their ID (already default)
- Optionally add your ID: `OWNER_DISCORD_ID=` or `OWNER_DISCORD_IDS=id1,id2`

### C. Run

```powershell
.\scripts\setup_wizard.py   # if .env not filled
.\scripts\start.ps1
```

Reviewers can chat in **DM** or in the configured **test channel**.

## 3. Bot state files (after a real conversation)

Chat 10–20 turns (name, hobbies, tone), then export:

```powershell
.\.venv\Scripts\python scripts\export_brain.py
```

Send the zip or files under `submission/brain/`:

- `identity.md` — who the bot became
- `relationship.md` — owner + bond (+ meta block)

## 4. Loom (~5 minutes)

Suggested outline:

1. **Architecture** — `bot.py` → `CompanionAgent` → `Brain` (2 markdown files) + `ProactiveScheduler`
2. **Memory** — consolidation after each turn; no full transcript; `identity.md` / `relationship.md`
3. **Proactive** — scheduled + LLM motivation; backoff when ignored
4. **Demo** — fresh brain → a few messages → show files changing
5. **Improvements** — multi-user brains, voice, better stage detection, etc.

## Quick verification

```powershell
.\.venv\Scripts\python scripts\check_setup.py
```

Should report allowed owners (including `cm6550`) and pass once tokens are set.
