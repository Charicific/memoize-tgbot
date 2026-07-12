<table>
<tr>
<td width="200" valign="middle" align="center">
<img src="assets/Memoize.png" alt="Memoize Bot Icon" width="180" />
</td>
<td valign="middle">

# Memoize

**Transform your LeetCode grind into something you actually look forward to.**

[![Try on Telegram](https://img.shields.io/badge/Try%20Memoize-@MemoizeLC__bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/MemoizeLC_bot?start)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-009688?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[![Infrastructure Cost](https://img.shields.io/badge/Infrastructure%20Cost-₹0%2Fmonth-brightgreen?style=flat-square)](https://koyeb.com)
[![Deployment](https://img.shields.io/badge/Deployed%20on-Koyeb-blueviolet?style=flat-square&logo=docker)](https://koyeb.com)
[![AI Powered](https://img.shields.io/badge/AI-Multi--Provider-orange?style=flat-square)](https://console.groq.com)
[![Spaced Repetition](https://img.shields.io/badge/Algorithm-SM--2%20Spaced%20Repetition-critical?style=flat-square)](https://supermemo.guru/wiki/SM-2)

> **Daily Challenges · 1v1 Battles · AI Coaching · Spaced Repetition · Streaks · Leaderboards**
> No new apps. No extra tabs. Just Telegram.

</td>
</tr>
</table>

---

## Table of Contents

- [What is Memoize?](#-what-is-memoize)
- [Feature Overview](#-feature-overview)
- [Command Reference](#-command-reference)
- [Architecture](#️-architecture)
- [Background Jobs](#-background-jobs)
- [Database Schema](#-database-schema)
- [Role Hierarchy](#-role-hierarchy)
- [Project Structure](#-project-structure)
- [Local Setup](#-local-setup)
- [Environment Variables](#-environment-variables)
- [Testing](#-testing)
- [Production Deployment](#-production-deployment)
- [Infrastructure Cost](#-infrastructure-cost)
- [Contributing](#-contributing)
- [License](#-license)

---

## What is Memoize?

Memoize is a **Telegram-native LeetCode companion** that meets you where you already are — no extra apps, no browser tabs, no context-switching. It wraps the full DSA practice loop into a single bot:

| Without Memoize | With Memoize |
|---|---|
| Manually check LeetCode daily | Daily challenge auto-delivered every morning |
| Screenshot to prove you solved it | Real-time submission verification via LeetCode API |
| Forget problems after solving them | SM-2 algorithm schedules optimal review dates |
| Stuck on a problem, no guidance | Progressive AI hints that nudge, not spoil |
| Losing motivation solo | 1v1 battles and group leaderboards |

> **[Start using Memoize now →](https://t.me/MemoizeLC_bot?start)**

---

## Feature Overview

### Daily Challenges & Contest Alerts

The bot automatically delivers **LeetCode's Daily Coding Challenge** to your groups and DMs every morning — complete with difficulty badge, topic tags, and formatted problem description. Contest alerts fire at four checkpoints:

- When registration opens
- 12 hours before start
- 5 minutes before start
- 10 minutes after end (results ping)

---

### 1v1 & Group Battles

Challenge any linked user to a **timed coding duel**. The bot polls both players' LeetCode submission histories every minute to verify who solved the battle problem first — no screenshots, no honor system, no disputes.

**How it works:**
1. `/battle @user` — challenger picks an opponent and optionally filters by difficulty/tag
2. Opponent receives a challenge notification and accepts/declines
3. Bot assigns a problem and starts the timer simultaneously for both
4. Submission poller detects the winning solve within ~60 seconds
5. XP and coins are awarded automatically; result is posted in the group

**Group battles** support open lobbies — post `/battle open` and multiple players can join before the timer starts.

Participants can propose a **draw** (`/stopbattle`), **pause** (`/pausebattle`), or **resume** (`/resumebattle`) — each action requires the other party's agreement.

---

### Spaced Repetition (SM-2)

Every problem you log via `/solved` is scheduled for review using the **SuperMemo SM-2 algorithm** — the same science behind Anki.

**The review loop:**
1. `/solved two-sum` — logs the problem and schedules first review
2. On review day, the bot sends a reminder: *"Time to recall: Two Sum"*
3. You attempt the problem, then rate your recall from **0 (blackout) to 5 (perfect)**
4. SM-2 recalculates the **ease factor** and **next interval** (1 day → 6 days → grows exponentially)
5. Problems you struggle with resurface sooner; mastered ones fade into long-term review

This turns your solve log into a **long-term memory system**, not just a history list.

---

### AI Coaching

Four distinct AI commands powered by **Groq** and **OpenRouter (fallback)**:

| Command | What it does | Model |
|---|---|---|
| `/hint <slug>` | Progressive hints unlocked one at a time: conceptual → strategic → pseudocode | Groq: `openai/gpt-oss-120b` (Fallback: OpenRouter `google/gemma-4-31b-it:free`) |
| `/analyze <code>` | Big-O time & space complexity breakdown with explanation | Groq: `openai/gpt-oss-120b` (Fallback: OpenRouter `google/gemma-4-31b-it:free`) |
| `/review <code>` | Correctness check, edge case coverage, refactoring suggestions | Groq: `llama-3.3-70b-versatile` (Fallback: OpenRouter `google/gemma-4-31b-it:free`) |
| `/visualize <code>` | Mermaid control-flow diagram + variable state trace | Groq: `llama-3.3-70b-versatile` (Fallback: OpenRouter `google/gemma-4-31b-it:free`) |

The hint system is intentionally **progressive** — you can't skip to the answer. Each call unlocks only the next level, preserving the learning value of the struggle.

---

### Streaks

Two independent streak systems run in parallel:

- **Activity Streak** — pulled directly from your LeetCode submission calendar
- **DCC Streak** — tracks consecutive days you completed the *Daily Coding Challenge* specifically

Both are tracked with timezone awareness and visible on your `/profile`. If you solved something on LeetCode but forgot to `/solved` in the bot, the scheduler **auto-logs it** for you so your streak stays intact.

---

### Leaderboards & Gamification

| Action | XP | Coins |
|---|---|---|
| Link + verify account | +50 | +50 |
| Win a 1v1 battle | +100 | +20 |
| Lose a 1v1 battle | +20 | — |
| Auto-logged streak solve | +15 | +5 |

XP feeds into a **level system** visible on `/profile`. Group leaderboards (`/leaderboard`) rank the top 10 in the current chat; `/gleaderboard` shows the global top 10.

---

### Conversational Fallback

Don't know where to start? Just message the bot in plain text. It routes your input through a keyword classifier that detects topics like linking, battles, SRS, AI coaching, streaks, and greetings — then responds with contextual guidance and inline buttons pointing to the right commands. Follow-up questions within the same topic are handled using a 5-minute context window stored in Redis.

---

## Command Reference

### User Commands

| Command | Description |
|---|---|
| `/start` | Onboarding & welcome. Supports deep-linked challenge redirects |
| `/help` | Full interactive help dashboard |
| `/link <leetcode_username>` | Start account linking — generates a one-time verification code |
| `/verify` | Scans your LeetCode bio to confirm the code and award 50 XP + 50 coins |
| `/unlink` | Disconnect your LeetCode account |
| `/profile` | View level, XP, coins, LeetCode stats, and global rank |
| `/streak` | Current activity streak from your LeetCode submission calendar |
| `/dstreak` | Consecutive daily coding challenge streak |
| `/daily` | Fetch today's LeetCode Daily Coding Challenge |
| `/random [difficulty] [tag]` | Random free problem matching optional filters |
| `/contest` | Upcoming contests with live countdowns |
| `/solved [slug] [quality]` | Log a solved problem and schedule it for SM-2 review |
| `/solve <query>` | Look up details and direct solve links for any LeetCode problem |
| `/reviews` | View your active Spaced Repetition (SRS) queue and master due items |
| `/rm_srs <query>` | Remove a problem from your active Spaced Repetition queue |
| `/hint <slug>` | Unlock the next progressive AI hint for a problem |
| `/analyze <code>` | Big-O time & space complexity analysis |
| `/review <code>` | AI code review: correctness, edge cases, optimizations |
| `/visualize <code>` | Control-flow Mermaid diagram + variable state trace |
| `/reminders` | Toggle daily challenge, streak warning, and contest alerts |
| `/leaderboard` | Top 10 in the current group by XP |

> 💡 **Tip:** You can use a dot `.` prefix instead of a slash `/` for all commands (e.g. `.ping`, `.daily`, or `.solved 1 4` work identically to their slash equivalents).

---

### Group Commands

| Command | Who | Description |
|---|---|---|
| `/gleaderboard` | Everyone | Global top 10 by XP |
| `/battle @user` | Everyone | Start a direct 1v1 battle with a specific user |
| `/battle open [difficulty] [tag]` | Everyone | Create an open lobby that anyone can join |
| `/stopbattle [uuid]` | Participant / Admin | Propose a draw or cancel a battle |
| `/pausebattle [uuid]` | Participant | Propose to freeze the battle timer |
| `/resumebattle [uuid]` | Participant | Propose to resume a paused battle |
| `/myrole` | Everyone | View your security role in this chat |
| `/config_group <setting> <enable/disable>` | Group Admin | Toggle `battles` or `feed` alerts for the group |
| `/mute_battle <user> <on/off>` | Group Owner | Mute a member from battle participation |
| `/clear_group_history` | Group Owner | Reset all leaderboard data for the group |

---

### Coordinator & Admin Commands

| Command | Role Required | Description |
|---|---|---|
| `/ping` | Coordinator | Check Telegram API & DB latency |
| `/stats` | Coordinator | Bot-wide usage statistics |
| `/pban <user> [reason]` | Coordinator | Globally ban a user from all bot interactions |
| `/unpban <user>` | Coordinator | Lift a global ban |
| `/forceverify <user> <leetcode>` | Coordinator | Instantly link and verify an account |
| `/userinfo <user>` | Coordinator | Full inspection of a user's record |
| `/activebattles` | Coordinator | List all active and paused battles across all groups |
| `/setrole <user> <COORDINATOR/USER>` | Super Admin | Promote or demote a user's global role |
| `/maintenance [on/off]` | Super Admin | Toggle global maintenance mode |
| `/pbroadcast <message>` | Super Admin | Broadcast message to all users in private DMs |
| `/gbroadcast <message>` | Super Admin | Broadcast message to all active groups |
| `/cbroadcast <message>` | Super Admin | Broadcast message to all tracked channels |
| `/broadcast <message>` | Super Admin | Broadcast message universally to private DMs, groups, and channels |

---

## Architecture

The bot runs as a containerized **FastAPI + aiogram** application. All components are on free tiers.

```
┌──────────────────────────────────────────────────────────────┐
│                       Telegram Client                        │
└────────────────────────────┬─────────────────────────────────┘
                             │  HTTPS Webhook / Long Poll
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    aiogram Dispatcher                        │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │                  Middleware Stack                    │   │
│   │   BanCheck → MaintenanceCheck → GroupMemberSync      │   │
│   └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│   ┌──────────────────────────▼───────────────────────────┐   │
│   │               Handler Routers                        │   │
│   │  common · daily · srs · ai · community · admin       │   │
│   └──────────────────────────┬───────────────────────────┘   │
└────────────────────────────┬─┘───────────────────────────────┘
                             │                                 
┌────────────────────────────▼─────────────────────────────────┐
│                      Service Layer                           │
│                                                              │
│  ┌─────────────────────┐   ┌──────────────────────────────┐  │
│  │  LeetCodeClient     │   │  AIService                   │  │
│  │  (GraphQL / httpx)  │   │  (Groq/NVIDIA/OpenRouter)    │  │
│  └─────────────────────┘   └──────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────┐   ┌──────────────────────────────┐  │
│  │  SupabaseDB         │   │  SRSService                  │  │
│  │  (asyncpg pool)     │   │  (SuperMemo SM-2 engine)     │  │
│  └─────────────────────┘   └──────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────┐                                     │
│  │  RedisCacheManager  │                                     │
│  │  (FSM · rate limits │                                     │
│  │   · role cache)     │                                     │
│  └─────────────────────┘                                     │
└──────────────────┬───────────────────────────────────────────┘
                   │
       ┌───────────┴──────────────┐
       │                          │
┌──────▼──────────────┐  ┌────────▼───────────────────────────┐
│  Supabase           │  │  APScheduler (Postgres jobstore)   │
│  · PostgreSQL DB    │  │  · Battle poller       (1 min)     │
│  · asyncpg pool     │  │  · SRS reminders       (9:00 AM)   │
│                     │  │  · Streak warnings     (3:00 PM)   │
│  Upstash Redis      │  │  · Feed & contest poll (5 min)     │
│  · FSM state        │  │  · Missed job recovery (on boot)   │
│  · Rate limiter     │  └────────────────────────────────────┘
│  · Role cache (5m)  │
└─────────────────────┘
```

### Stack at a Glance

| Layer | Technology | Purpose |
|---|---|---|
| Bot Framework | [aiogram 3](https://docs.aiogram.dev/) | Async Telegram bot framework |
| Web Server | FastAPI + Uvicorn | Webhook endpoint & health check |
| Database | Supabase (PostgreSQL) | Persistent storage via asyncpg |
| Cache & FSM | `cachetools` (L1) + Upstash Redis (L2) | Dual-tier hybrid cache-aside layer & bot FSM state |
| LeetCode Data | LeetCode GraphQL API | Problem fetch, submission polling |
| AI — Hints & Analysis | Groq (openai/gpt-oss-120b) | Fast inference for hints & complexity |
| AI — Review & Visualize | NVIDIA Build (Qwen-3 / DeepSeek-V3) | Deep code review and flowchart visualization |
| Background Jobs | APScheduler | Cron-style persistent scheduled tasks |
| Deployment | Koyeb (Docker) | Containerized cloud hosting |

### Hybrid Caching (L1/L2 Cache-Aside)

To avoid database connection bottlenecking and network latency overhead:
1. **L1 RAM Cache:** Short-term (60s - 5m) local `TTLCache` in the python application process. Delivers instantaneous `0.001ms` lookups for hot keys (settings, user mutes, links, roles).
2. **L2 Shared Cache:** Upstash Redis is queried on L1 cache misses to avoid querying PostgreSQL directly (~2ms - 5ms network lookup).
3. **Negative Caching:** Cache misses (e.g. checking ban status or profiles for unregistered users) are cached using `__none__` sentinels for 5 minutes, protecting Supabase from high-concurrency group chat traffic.
4. **Auto-Eviction / Write-Through:** Cache keys are automatically invalidated on any user profile updates, settings changes, or mutes.

---

## Background Jobs

Five scheduled tasks run concurrently via `APScheduler`. Job state persists in Supabase PostgreSQL so no jobs are lost on container restart.

| Job | Frequency | What it does |
|---|---|---|
| `poll_active_battles` | Every 1 min | Polls LeetCode submissions for active battles. Detects solves, crowns a winner, distributes XP/coins, and expires timed-out battles. |
| `check_srs_reviews` | Daily at 9:00 AM | Finds users with SM-2 review items due today and sends reminder DMs. Skips users already notified today (Redis dedup). |
| `check_streak_reminders` | Daily at 3:00 PM UTC | Checks LeetCode submission calendars. Auto-logs today's solve if found on LeetCode but not in the bot (+15 XP, +5 coins). Sends a streak warning DM if no solve is detected. |
| `poll_leetcode_feed` | Every 5 min | Scrapes the daily challenge and upcoming contests. Broadcasts daily challenge cards to all feed-enabled groups. Fires contest alerts at registration, 12h, 5min, and 10min-after checkpoints. |
| `check_missed_jobs` | Once on boot | Compares current time against daily job milestones. Immediately triggers any cron job the bot missed while it was offline. |

---

## Database Schema

12 tables covering users, account links, battle sessions, spaced repetition state, group memberships, group settings, daily challenge history, and bot channels tracking.

Full definitions: [`database/schema.sql`](database/schema.sql)

### Key Tables

| Table | Purpose |
|---|---|
| `users` | XP, level, coins, global role, ban status, notification preferences |
| `linked_accounts` | Telegram ↔ LeetCode username mapping with verification flow state |
| `battles` | 1v1 battle state machine (`PENDING → ACTIVE → COMPLETED / EXPIRED / CANCELLED`) |
| `group_battles` | Multiplayer open-lobby battle sessions |
| `group_battle_participants` | Per-participant join time, solve timestamp, and solve duration |
| `srs_reviews` | SM-2 parameters per problem: ease factor, interval, repetitions, next review date |
| `problem_history` | Solve log used for streak calculation and auto-solve detection |
| `group_members` | Tracks which users belong to which groups (feeds leaderboards) |
| `group_settings` | Per-group toggles: `battles` and `feed` enabled/disabled |
| `group_battle_mutes` | Users muted from battle participation by a group owner |
| `daily_challenges` | Historical daily challenge log (date → problem slug) for DCC streak tracking |
| `bot_channels` | Tracks Telegram channels the bot is active in (for broadcasts) |

### SM-2 Parameters Explained

| Field | Meaning |
|---|---|
| `ease_factor` | How easily you recall this problem (starts at 2.5, floor at 1.3) |
| `interval` | Days until next review — grows exponentially with each successful recall |
| `repetitions` | Number of consecutive successful reviews (resets to 0 on low recall) |
| `next_review_date` | Timestamp for the next scheduled reminder DM |

---

## Role Hierarchy

```
SUPER_ADMIN  ──►  COORDINATOR  ──►  GROUP_OWNER  ──►  GROUP_ADMIN  ──►  USER
```

| Role | Storage | Capabilities |
|---|---|---|
| `USER` | Default | Full access to practice features, AI coaching, and personal stats |
| `GROUP_ADMIN` | Resolved via Telegram API | Configure group settings (`/config_group`) |
| `GROUP_OWNER` | Resolved via Telegram API | Mute battle participants, reset group history |
| `COORDINATOR` | Stored in DB (`users.role`) | Moderation, inspection, global ban/unban |
| `SUPER_ADMIN` | Defined in `.env` | Full system control: broadcast, maintenance mode, role assignment |

> **Caching:** Resolved roles are cached in Redis for **5 minutes**. A `/setrole` change immediately invalidates all cached role entries for that user across every group.

---

## Project Structure

```
memoize-tgbot/
│
├── database/
│   └── schema.sql                   # Full PostgreSQL schema (11 tables)
│
├── src/
│   ├── config.py                    # Pydantic Settings — loads & validates all env vars
│   ├── main.py                      # Bot startup, webhook/polling, FastAPI health endpoint
│   │
│   ├── handlers/                    # aiogram routers — one module per feature domain
│   │   ├── admin.py                 # Coordinator & Super Admin commands
│   │   ├── ai.py                    # /hint, /analyze, /review, /visualize
│   │   ├── chat.py                  # Conversational fallback & keyword-based routing
│   │   ├── common.py                # /start, /link, /verify, /profile, /reminders
│   │   ├── community.py             # /battle, /leaderboard, group controls
│   │   ├── daily.py                 # /daily, /random, /contest
│   │   ├── srs.py                   # /solved, spaced repetition logging & grading
│   │   ├── streaks.py               # /streak, /dstreak — submission calendar parsing
│   │   └── visualize.py             # Mermaid diagram generation & variable trace
│   │
│   ├── middlewares/
│   │   ├── ban_middleware.py         # Blocks banned users before any handler runs
│   │   └── maintenance_middleware.py # Short-circuits all non-admin handlers in maintenance mode
│   │
│   ├── services/                    # Core business logic & external integrations
│   │   ├── leetcode.py              # LeetCode GraphQL client (httpx, async)
│   │   ├── supabase_db.py           # asyncpg connection pool wrapper & all DB queries
│   │   ├── redis_cache.py           # Cache manager: FSM, rate limits, role cache
│   │   ├── ai_service.py            # Multi-provider client wrapper (Groq, NVIDIA, OpenRouter)
│   │   └── srs_service.py           # SuperMemo SM-2 algorithm implementation
│   │
│   └── utils/
│       ├── formatters.py            # HTML parser, markdown cleaner, content sanitization
│       ├── logging_helper.py        # Sends structured audit logs to a Telegram log channel
│       └── roles.py                 # Role resolution logic with Redis caching
│
├── tests/
│   ├── test_leetcode_mock.py        # Offline unit tests with mocked HTTP responses
│   └── test_leetcode.py             # Live integration tests against LeetCode's API
│
├── Dockerfile                       # Multi-stage Python Docker build
├── Procfile                         # Koyeb / Heroku process definition
├── requirements.txt
└── runtime.txt                      # python-3.11.x
```

---

## Local Setup

### Prerequisites

| Service | What you need | Link |
|---|---|---|
| Python | 3.11 or higher | [python.org](https://python.org) |
| Telegram | Bot token from BotFather | [@BotFather](https://t.me/BotFather) |
| Supabase | Project URL + anon key + DB URL | [supabase.com](https://supabase.com) |
| Upstash | Redis connection URL | [upstash.com](https://upstash.com) |
| NVIDIA | API key (free tier) | [integrate.api.nvidia.com](https://integrate.api.nvidia.com) |
| OpenRouter | API key (optional fallback) | [openrouter.ai](https://openrouter.ai) |

---

### Step-by-Step

**1. Clone the repository**
```bash
git clone https://github.com/Charicific/memoize-tgbot.git
cd memoize-tgbot
```

**2. Create and activate a virtual environment**
```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Copy the template below into a `.env` file at the project root:

```env
# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# ─── Supabase ────────────────────────────────────────────────
SUPABASE_URL=https://your_ref.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_DB_URL=postgresql+asyncpg://postgres:your_password@db.your_ref.supabase.co:5432/postgres

# ─── Upstash Redis ───────────────────────────────────────────
REDIS_URL=rediss://default:your_password@your_endpoint.upstash.io:6379

# ─── AI Keys ─────────────────────────────────────────────────
GROQ_API_KEY=your_groq_api_key
NVIDIA_API_KEY=your_nvidia_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# ─── Server ──────────────────────────────────────────────────
PORT=8000

# ─── Optional: Webhook (omit to use long-polling mode) ───────
# WEBHOOK_URL=https://your-app.koyeb.app

# ─── Optional: Admin Configuration ──────────────────────────
# SUPER_ADMIN_IDS=123456789,987654321
# LOG_CHANNEL_ID=-100xxxxxxxxxx

# ─── Optional: UptimeRobot Monitoring ───────────────────────
# UPTIMEROBOT_API_KEY=your_api_key_here
# UPTIMEROBOT_MONITOR_ID=your_monitor_id_here
```

> **Tip:** Omitting `WEBHOOK_URL` automatically switches the bot to **long-polling mode** — no public URL or ngrok tunnel needed for local development.

**5. Apply the database schema**

Open the [Supabase SQL Editor](https://supabase.com/dashboard), select your project, and run the contents of [`database/schema.sql`](database/schema.sql).

**6. Start the bot**
```bash
python -m src.main
```

The bot should appear online in your Telegram client within a few seconds.

---

## Environment Variables

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `SUPABASE_URL` | Your Supabase project REST URL |
| `SUPABASE_KEY` | Supabase anon / service-role key |
| `SUPABASE_DB_URL` | `postgresql+asyncpg://...` direct connection string |
| `REDIS_URL` | Upstash Redis `rediss://` URL |
| `GROQ_API_KEY` | Groq API key for primary `/hint` and `/analyze` calls |
| `NVIDIA_API_KEY` | NVIDIA API key for primary `/review` and `/visualize` calls |
| `OPENROUTER_API_KEY` | OpenRouter API key for rate-limit fallbacks (optional) |
| `PORT` | Port for Uvicorn / FastAPI (default: `8000`) |
| `WEBHOOK_URL` | Public HTTPS URL; omit to use long-polling mode |
| `SUPER_ADMIN_IDS` | Comma-separated Telegram user IDs with super admin access |
| `LOG_CHANNEL_ID` | Telegram channel ID for admin audit logs |

---

## Testing

The test suite is split into two layers:

### Offline Mock Tests *(no API keys required)*

```bash
pytest tests/test_leetcode_mock.py -v
```

Uses mocked HTTP responses to validate LeetCode client logic without hitting any external API.

### Live Integration Tests *(requires internet; hits the real LeetCode GraphQL API)*

```bash
# Windows (PowerShell)
$env:PYTHONIOENCODING = "utf-8"
python tests/test_leetcode.py

# macOS / Linux
PYTHONIOENCODING=utf-8 python tests/test_leetcode.py
```

> The `PYTHONIOENCODING` flag prevents Unicode console errors on Windows when printing problem titles with non-ASCII characters.

---

## Production Deployment

The project is Docker-ready and configured for **[Koyeb](https://koyeb.com)** (recommended) or any Docker-compatible platform.

### Koyeb (Recommended)

1. **Push your repo to GitHub** and connect it to Koyeb via the dashboard.
2. **Set all environment variables** in Koyeb's environment config, adding:
   ```
   WEBHOOK_URL=https://your-app-name.koyeb.app
   ```
   With `WEBHOOK_URL` set, the bot switches from polling to **webhook mode** automatically.
3. Koyeb auto-detects the `Dockerfile` / `Procfile` and starts Uvicorn — no extra config needed.
4. **Keep the container warm** by pointing a free [UptimeRobot](https://uptimerobot.com) monitor at:
   ```
   https://your-app-name.koyeb.app/health
   ```

### Manual Docker

```bash
docker build -t memoize-tgbot .
docker run --env-file .env -p 8000:8000 memoize-tgbot
```

### Health Check

The FastAPI server exposes `/health`, used for uptime monitoring and deployment readiness:

```json
{ "status": "ok", "telegram": "reachable", "db": "reachable" }
```

---

## Infrastructure Cost

> **Total: ₹0/month.** Every component runs on a free tier.

| Service | What it provides | Free tier limit | Cost |
|---|---|---|---|
| [Koyeb](https://koyeb.com) | Container hosting | 1 free instance | **₹0** |
| [Supabase](https://supabase.com) | PostgreSQL + connection pooling | 500 MB storage, 2 GB transfer | **₹0** |
| [Upstash](https://upstash.com) | Redis (FSM + rate limits + cache) | 10K requests/day | **₹0** |
| [Groq](https://console.groq.com) | `/hint` and `/analyze` inference | Rate-limited free tier | **₹0** |
| [NVIDIA](https://build.nvidia.com) | `/review` and `/visualize` inference | Free trial quota (1,000 credits) | **₹0** |
| [OpenRouter](https://openrouter.ai) | Fallback free-tier models | Free tier endpoints | **₹0** |
| [UptimeRobot](https://uptimerobot.com) | Uptime monitoring | 50 monitors | **₹0** |

---

## Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feat/your-feature-name`
3. **Commit your changes**: `git commit -m 'feat: add your feature'`
4. **Push the branch**: `git push origin feat/your-feature-name`
5. **Open a Pull Request** — describe what you changed and why

### Good First Issues

- Add new LeetCode GraphQL query fields to [`leetcode.py`](src/services/leetcode.py) (e.g. contest rating history)
- Improve AI prompt templates in [`ai_service.py`](src/services/ai_service.py) for better hint quality
- Expand `/profile` to display SM-2 statistics (total reviews, retention rate, due count)
- Write additional mock unit tests for the SRS and battle service logic
- Add difficulty breakdown (Easy / Medium / Hard counts) to the `/stats` admin command

Found a bug? [Open an issue](https://github.com/Charicific/memoize-tgbot/issues) with steps to reproduce.

---

## License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE) for full details.

---

<div align="center">

Built with `asyncio` and too many LeetCode problems.

**[Try Memoize on Telegram →](https://t.me/MemoizeLC_bot?start)**

<br/>

*If Memoize helped you crack a hard problem or land an offer, drop a ⭐ on the repo!*

</div>
