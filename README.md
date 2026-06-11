# Server Memory Bot

A Discord bot with two genuinely useful, AI-powered features built on one engine:

- **🧠 Memory — "ask the server anything."** The bot quietly indexes message
  history and answers natural-language questions about it
  (`/ask what did we decide about the meeting time?`).
- **🛡️ Moderation — smart flagging + graduated action.** Optionally, it reads
  messages, flags *genuinely* problematic ones (harassment, threats, scams), and
  takes a measured action — **it never bans**:
  - low / medium severity → **warns** the user (DM)
  - high severity → **mutes** the user via Discord timeout + warns
  - staff are never auto-actioned, only logged

  Every action is reported to a mod-only channel **with the reasoning attached**,
  so a human can review and reverse it. No dumb word filters.

Stored messages are **automatically deleted after 3 days** (configurable), so the
bot keeps only a recent rolling window of history.

It's fully self-contained: message history lives in a local **SQLite** database
with full-text search (FTS5), so there's **no external vector database or
embeddings service to run**. The AI answering and moderation use the
**Claude API** (Anthropic).

---

## How it works

```
Discord message ──▶ stored in SQLite (FTS5 full-text index)
                          │
/ask "..."  ──▶ search history for relevant messages ──▶ Claude ──▶ cited answer
                          │
(optional) each message ──▶ Claude classifier ──▶ flag to #mod-log if problematic
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Open **Bot** → **Add Bot**, then **Reset Token** and copy the token.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
   (the bot needs this to read messages).
4. Under **OAuth2 → URL Generator**, select the `bot` and
   `applications.commands` scopes. Give it **Send Messages** + **Read Message
   History**, and — if you'll use moderation — **Timeout Members** (so it can
   mute). Then open the generated URL to invite it to your server. The bot's
   role must sit **above** the roles of members you want it to be able to mute.

### 3. Get a Claude API key

Create one at the [Anthropic Console](https://console.anthropic.com/).

### 4. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in `DISCORD_TOKEN` and `ANTHROPIC_API_KEY`. The `.env`
file is gitignored, so your secrets never get committed.

### 5. Run

```bash
python bot.py
```

---

## Commands

| Command         | What it does                                                     |
| --------------- | --------------------------------------------------------------- |
| `/ask <question>` | Answers a question using the server's indexed message history. |
| `/forget_me`    | Deletes your stored messages and stops indexing you (privacy).  |
| `/remember_me`  | Opts you back in to indexing.                                   |

---

## Enabling moderation (optional)

Moderation is **off by default** because it calls the Claude API on every
message, which adds cost and can hit rate limits on busy servers. To turn it on:

1. Create a private `#mod-log` channel only your moderators can see.
2. Right-click it → **Copy Channel ID** (enable Developer Mode in Discord
   settings if you don't see this).
3. In `.env`:
   ```env
   MODERATION_ENABLED=true
   MOD_LOG_CHANNEL_ID=123456789012345678
   ```
4. (Optional) tune the mute duration and model:
   ```env
   MUTE_MINUTES=60
   MODERATION_MODEL=claude-haiku-4-5   # cheaper/faster for high-volume servers
   ```

The bot **warns** (low/medium) or **mutes via Discord timeout** (high) — it never
bans, and it never auto-actions staff. Every action is logged to the mod channel
for review. Keep a human in the loop.

---

## Privacy

This bot stores message history, so handle it responsibly:

- Secrets live in `.env`, which is **gitignored** and never committed.
- The SQLite database (`*.db`) is also gitignored.
- Stored messages are **auto-deleted after `RETENTION_DAYS` (default 3)** — the
  bot sweeps on startup and every 6 hours, so it only ever holds a recent window.
- Users can run `/forget_me` to delete their data and opt out of indexing.
- Tell your community the bot is active and what it stores.

### Keeping the source code private

The code itself is in a Git repository. To keep that repository private on GitHub:

- **Web:** Repo → **Settings** → **General** → scroll to **Danger Zone** →
  **Change repository visibility** → **Private**.
- **CLI:** `gh repo edit <owner>/<repo> --visibility private`
- When creating a new repo, just choose **Private** at creation time.

Private repos are only visible to you and collaborators you explicitly add.

---

## Project layout

```
bot.py              # entry point — boots the bot, loads cogs
config.py           # env-var configuration
db.py               # SQLite + FTS5 message store
claude_client.py    # Claude API calls (answering + moderation)
cogs/
  memory.py         # indexing + /ask + /forget_me + /remember_me
  moderation.py     # smart flagging to a mod channel
```
