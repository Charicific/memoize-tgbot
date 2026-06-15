# Telegram LeetCode Companion — Complete Project Guide (A to Z)

Welcome to the comprehensive, definitive developer and architect guide for the **LeetCode Companion Bot**. This document provides an exhaustive, end-to-end breakdown of the project’s vision, system architecture, database design, security layers, background schedulers, service modules, command handlers, and deployment workflows.

---

## Table of Contents
1. [Project Vision & Product Concept](#1-project-vision--product-concept)
2. [System Architecture & Data Flows](#2-system-architecture--data-flows)
3. [Database Schemas & Data Models](#3-database-schemas--data-models)
4. [Middlewares & Security Layer](#4-middlewares--security-layer)
5. [Dynamic Role Resolution & Hierarchy](#5-dynamic-role-resolution--hierarchy)
6. [Background Schedulers & Workers](#6-background-schedulers--workers)
7. [Service Layer Implementations](#7-service-layer-implementations)
8. [Command Dictionary (36 Commands)](#8-command-dictionary-36-commands)
9. [Project Directory Structure](#9-project-directory-structure)
10. [Local Setup, Testing & Deployment](#10-local-setup-testing--deployment)

---

## 1. Project Vision & Product Concept

The LeetCode Companion Bot is not a LeetCode alternative. It is a **Telegram-native companion platform** designed to transform the DSA practice journey from a lonely, browser-locked grind into a highly retentive, gamified, and social learning habit.

### Core Value Propositions
* **Meet Users Where They Live:** Instead of asking developers to open browser tabs or check dashboards, the bot sends daily tasks, contest updates, and peer battles directly to their Telegram groups and DMs.
* **SuperMemo SM-2 Spaced Repetition:** Implements algorithmic retention schedules for solved problems, pushing reviews dynamically to overcome the forgetting curve.
* **1v1 Real-Time Peer Battles:** Gamifies learning through multiplayer coding battles. The bot automatically polls LeetCode submissions to verify solutions and award XP and coins.
* **Progressive AI Coaching:** Integrates Groq and Gemini APIs to offer conceptual, strategic, and pseudocode hints step-by-step, helping users solve problems without spoiling the solution.
* **₹0 Infrastructure cost:** Uses a carefully designed serverless, containerized, and free-tier-native stack (Koyeb, Supabase, Upstash Redis, Groq, Gemini) requiring zero operational expenses.

---

## 2. System Architecture & Data Flows

The application runs as a containerized FastAPI application wrapped around the asynchronous `aiogram` Telegram bot framework. It is configured for high performance, relying on a direct connection pool to Supabase PostgreSQL and Upstash Redis for session state (FSM) and rate-limiting.

```mermaid
graph TB
    subgraph TelegramClient["Telegram Client Context"]
        User["Telegram User"]
        Group["Group / Supergroup"]
    end

    subgraph BotCore["Koyeb Container (FastAPI + aiogram)"]
        main["main.py (App Lifecycle)"]
        dp["Dispatcher & Routers"]
        
        subgraph Middlewares["Request Pipeline"]
            GroupMember["GroupMemberMiddleware"]
            BanCheck["BanCheckMiddleware"]
            MaintenanceCheck["MaintenanceCheckMiddleware"]
        end
        
        subgraph Services["Service Modules"]
            lc["LeetCodeClient (GraphQL / httpx)"]
            db_client["SupabaseDB (asyncpg pool)"]
            cache["RedisCacheManager (redis-py)"]
            ai["AIService (Groq & Gemini)"]
            srs["SRSService (SM-2 Engine)"]
        end
        
        scheduler["APScheduler (Postgres Jobstore)"]
    end

    subgraph CloudData["Data & Caching Layer"]
        Supabase["Supabase DB (PostgreSQL)"]
        Upstash["Upstash Redis (FSM States & Limits)"]
    end

    subgraph ExternalAPIs["Third-Party APIs"]
        LeetCode["LeetCode API (GraphQL)"]
        Groq["Groq API (Llama 3.3)"]
        Gemini["Gemini API (Flash 2.0)"]
    end

    User -->|Commands / Callbacks| dp
    Group -->|Group Messages| dp
    dp --> Middlewares
    Middlewares --> Services
    
    scheduler -->|Interval Poll Battles| lc
    scheduler -->|Cron Daily SRS Checks| db_client
    scheduler -->|Cron Daily Streak Checks| db_client
    
    lc --> LeetCode
    db_client --> Supabase
    cache --> Upstash
    ai --> Groq
    ai --> Gemini
    srs --> db_client
```

---

## 3. Database Schemas & Data Models

The PostgreSQL database runs on Supabase. To maximize performance and bypass ORM overhead, the bot connects directly using the asynchronous `asyncpg` library with connection pooling. The schema is initialized and dynamically maintained in [src/services/supabase_db.py](file:///d:/Ongoing_projects/memoize-tgbot/src/services/supabase_db.py).

### Table Definitions

#### 1. `users`
Tracks individual user metadata, gamification metrics (XP, level, coins), notification preferences, and system access status.
```sql
CREATE TABLE users (
    telegram_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    coins INTEGER DEFAULT 0,
    remind_daily BOOLEAN DEFAULT TRUE,
    remind_streak BOOLEAN DEFAULT TRUE,
    remind_contests BOOLEAN DEFAULT TRUE,
    role VARCHAR(50) DEFAULT 'USER',       -- USER, COORDINATOR, SUPER_ADMIN
    is_banned BOOLEAN DEFAULT FALSE
);
```

#### 2. `linked_accounts`
Maps Telegram identities to LeetCode usernames. Employs a verification status flag.
```sql
CREATE TABLE linked_accounts (
    telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    leetcode_username VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(50),
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 3. `problem_history`
Maintains log records of solved LeetCode challenges. Used to calculate streak activity.
```sql
CREATE TABLE problem_history (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    problem_slug VARCHAR(255) NOT NULL,
    problem_title VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    solved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, problem_slug)
);
```

#### 4. `srs_reviews`
Logs memory parameters calculated using the SuperMemo SM-2 algorithm for spaced repetition.
```sql
CREATE TABLE srs_reviews (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    problem_slug VARCHAR(255) NOT NULL,
    ease_factor DOUBLE PRECISION DEFAULT 2.5,
    interval INTEGER DEFAULT 1,            -- review interval in days
    repetitions INTEGER DEFAULT 0,
    next_review_date TIMESTAMP WITH TIME ZONE NOT NULL,
    last_quality INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, problem_slug)
);
```

#### 5. `battles`
Stores metadata and session state for active, paused, completed, or expired 1v1 coding challenges.
```sql
CREATE TABLE battles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challenger_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    opponent_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    problem_slug VARCHAR(255) NOT NULL,
    problem_title VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',  -- PENDING, ACTIVE, COMPLETED, EXPIRED, PAUSED, CANCELLED, DECLINED
    winner_id BIGINT REFERENCES users(telegram_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    paused_at TIMESTAMP WITH TIME ZONE,
    remaining_seconds INT,
    chat_id BIGINT,
    message_id BIGINT
);
```

#### 6. `group_members`
Links users to Telegram groups they participate in, supporting group-level leaderboard aggregation.
```sql
CREATE TABLE group_members (
    group_id BIGINT,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, telegram_id)
);
```

#### 7. `daily_challenges`
Logs historical daily challenges scraped from LeetCode, correlating date with problem slug to compute Daily Coding Challenge (DCC) streaks.
```sql
CREATE TABLE daily_challenges (
    date DATE PRIMARY KEY,
    problem_slug VARCHAR(255) NOT NULL
);
```

#### 8. `group_settings`
Tracks customizable configurations per Telegram group (e.g. enabling feed updates or battle privileges).
```sql
CREATE TABLE group_settings (
    group_id BIGINT,
    setting_name VARCHAR(100),
    setting_value VARCHAR(255),
    PRIMARY KEY (group_id, setting_name)
);
```

#### 9. `group_battle_mutes`
Stores list records of members muted by the group owner from starting or accepting battle challenges within specific groups.
```sql
CREATE TABLE group_battle_mutes (
    group_id BIGINT,
    telegram_id BIGINT,
    muted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, telegram_id)
);
```

#### 10. `group_battles`
Stores metadata and session state for multiplayer group battle challenges.
```sql
CREATE TABLE group_battles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id BIGINT NOT NULL,
    problem_slug VARCHAR(255) NOT NULL,
    problem_title VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',  -- PENDING, ACTIVE, COMPLETED, CANCELLED
    created_by BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    starts_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    message_id BIGINT
);
```

#### 11. `group_battle_participants`
Stores participant lists, join times, and solve timestamps for multiplayer group battles.
```sql
CREATE TABLE group_battle_participants (
    group_battle_id UUID REFERENCES group_battles(id) ON DELETE CASCADE,
    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    solved_at TIMESTAMP WITH TIME ZONE,
    solve_time_seconds INT,
    PRIMARY KEY (group_battle_id, telegram_id)
);
```

---

## 4. Middlewares & Security Layer

Middlewares act as gateways in the bot request pipeline. They process and filter incoming updates (messages and callback queries) before they reach command handlers.

* **`GroupMemberMiddleware`**: Intercepts group and supergroup messages. Automatically calls `db.record_group_member` to ensure the sender is recorded as a member of the group, which sustains the group leaderboards.
* **`BanCheckMiddleware`**: Runs a quick check against Upstash Redis (falling back to Supabase DB) to see if `user:banned:<id>` is set. If the user is globally banned, the request is silently intercepted and dropped.
* **`MaintenanceCheckMiddleware`**: Reads `system:maintenance` from Redis. If enabled (`"1"`), it intercepts incoming requests. If the sender is not a `SUPER_ADMIN`, it replies with a stylized maintenance downtime notification and terminates processing.

---

## 5. Dynamic Role Resolution & Hierarchy

The application runs a unified security hierarchy using five distinct roles defined in [src/utils/roles.py](file:///d:/Ongoing_projects/memoize-tgbot/src/utils/roles.py):

```
[SUPER_ADMIN] ──► [COORDINATOR] ──► [GROUP_OWNER] ──► [GROUP_ADMIN] ──► [USER]
```

### Role Level Specifications
1. **`USER` (Value: 0):** Default registered account. Access to normal practice, AI commands, and individual SRS/stats.
2. **`GROUP_ADMIN` (Value: 1):** Contextual role. Dynamically resolved via Telegram API if the user is an administrator of the group chat where the command is executed. Access to `/config_group`.
3. **`GROUP_OWNER` (Value: 2):** Contextual role. Resolved if the user is the creator of the group chat. Access to `/mute_battle` and `/clear_group_history`.
4. **`COORDINATOR` (Value: 3):** Global role stored in Supabase (`users.role = 'COORDINATOR'`). Access to system inspection and moderation commands like `/pban`, `/unpban`, `/userinfo`, `/forceverify`, `/stats`, `/ping`, and `/activebattles`.
5. **`SUPER_ADMIN` (Value: 4):** Global role defined statically in `.env` (`super_admin_ids`). Complete command override. Access to promotion (`/setrole`), database operations, maintenance toggles (`/maintenance`), and broadcasts (`/broadcast`).

### Performance & Cache Eviction
To avoid exhausting database connections and hitting Telegram Bot API rate limits (via `bot.get_chat_member`), resolved roles are cached in Upstash Redis (`user:role:<chat_id>:<user_id>`) for 5 minutes.
Whenever a user's role is modified via `/setrole`, the bot automatically invalidates all keys matching `user:role:*:<target_id>` to ensure immediate enforcement.

---

## 6. Background Schedulers & Workers

Background scheduler routines run concurrently using the `AsyncIOScheduler` from `apscheduler`. The scheduler uses a persistent SQLAlchemy jobstore pointed at Supabase PostgreSQL to prevent jobs from being wiped when the server container restarts.

### Background Jobs Description

#### 1. `poll_active_battles` (Frequency: Every 1 minute)
* Retrieves all battles marked `ACTIVE` or `PENDING`.
* If a battle's expiration deadline has passed, updates status to `EXPIRED`, logs the occurrence to the admin channel, and DMs notification alerts to both competitors.
* For active battles, fetches both users' recent accepted submissions from the LeetCode GraphQL API. If it finds a submission timestamp matching the battle's `problem_slug` that occurred *after* the battle's `started_at` timestamp:
  * If both solved, determines the winner based on the earliest submission timestamp.
  * Updates battle status to `COMPLETED`, logs results, and distributes XP/coins (Winner: 100 XP + 20 coins, Loser: 20 XP).

#### 2. `check_srs_reviews` (Frequency: Daily at 9:00 AM Local Time)
* Queries Supabase for users with spaced repetition items due today (`next_review_date <= CURRENT_DATE`).
* Checks Redis cache to prevent duplicate notifications on the same calendar day.
* Sends private notification alerts prompting the user to run `/solved` to complete pending reviews.

#### 3. `check_streak_reminders` (Frequency: Daily at 15:00 UTC / 8:30 PM IST)
* Identifies users who have streak reminders enabled but haven't logged a solve today.
* Queries the LeetCode API for recent accepted submissions.
  * **Auto-Log Action:** If the user solved a problem on LeetCode today but forgot to log it, the bot **auto-logs the solve** to maintain the streak and awards 15 XP & 5 coins.
  * **Warning Action:** If no solve is found, the bot sends a **streak warning alert** prompting the user to solve a problem and log it using `/solved` to protect their streak.

#### 4. `poll_leetcode_feed` (Frequency: Every 5 minutes)
* Scrapes LeetCode API for the Daily Challenge and upcoming contests.
* **Daily Challenge:** If not already posted, logs the challenge to the DB, formats the description HTML, and broadcasts the card to all feed-enabled groups and DMs.
* **Contest Announcements:** Triggers active alerts:
  * *Registration:* When a new contest is scraped.
  * *12h Alert:* 12 hours before a contest begins.
  * *Start Alert:* 5 minutes before the contest starts.
  * *End Alert:* 10 minutes after a contest ends, prompting solution discussions.

#### 5. `check_missed_jobs` (Frequency: Runs 10 seconds after startup)
* Compares current time with expected cron milestones. If the bot was offline during scheduled daily checks (9:00 AM for SRS or 15:00 UTC for streaks), it triggers them immediately to prevent missed alerts.

---

## 7. Service Layer Implementations

The service modules under `src/services/` separate external API consumption and core math logic from the handler layers.

### `LeetCodeClient` ([src/services/leetcode.py](file:///d:/Ongoing_projects/memoize-tgbot/src/services/leetcode.py))
Handles GraphQL requests using `httpx`. It parses queries to LeetCode's undocumented official API. Key endpoints implemented:
* `get_daily_challenge`: Scrapes daily challenge metadata (slug, difficulty, title, HTML description).
* `get_user_profile`: Retrieves global ranking, registration info, and total solved statistics.
* `get_user_calendar`: Fetches the user's `submissionCalendar` JSON string to compute streaks.
* `get_recent_accepted_submissions`: Fetches the last 20 accepted submissions (slug, title, timestamp) to support battles and the `/solved` command.
* `get_problemset_questions`: Fetches a subset of questions filtered by difficulty and tag to populate random challenges.

### `RedisCacheManager` ([src/services/redis_cache.py](file:///d:/Ongoing_projects/memoize-tgbot/src/services/redis_cache.py))
Wraps `redis.asyncio` to interface Upstash serverless Redis. Key utilities:
* **FSM Storage:** Holds active aiogram Finite State Machine storage parameters.
* **Key-Value Cache:** Provides `get`, `set` (with TTL), and `delete` functions to cache heavy LeetCode queries and user profiles.
* **Token Bucket Rate Limiting:** Executes atomic checks. Limits users to a specified frequency (e.g., 5 requests per 10 seconds) using a Redis transaction to prevent API abuse.

### `SRSService` ([src/services/srs_service.py](file:///d:/Ongoing_projects/memoize-tgbot/src/services/srs_service.py))
Calculates retention scheduling parameters using the SuperMemo SM-2 algorithm:
```python
def calculate_sm2(quality: int, ease_factor: float, interval: int, repetitions: int):
    # Reset sequence if recall quality is low
    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1

    # Adjust ease factor based on quality score
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor) # Lower bound constraint

    return ease_factor, interval, repetitions
```
Calculates `next_review_date` by adding the scheduled interval (in days) to the current timestamp.

### `AIService` ([src/services/ai_service.py](file:///d:/Ongoing_projects/memoize-tgbot/src/services/ai_service.py))
Interfaces Groq and Gemini APIs to support the AI Coaching features.
* **`generate_progressive_hints` (Groq - Llama 3.3 70B):** Generates conceptual, strategic, and detailed pseudocode hints for a LeetCode problem.
* **`analyze_complexity` (Groq - Llama 3.3 70B):** Performs Big-O time and space complexity evaluations on code submissions.
* **`generate_code_review` (Gemini Flash 2.0):** Reviews structural correctness, identifies edge cases, evaluates readability, and provides refactored optimizations.

---

## 8. Command Dictionary (37 Commands)

The bot supports **37 commands** distributed across 7 handler modules. All command routes evaluate user roles before executing.

### General User Commands (18)
* `/start`: Welcome onboarding interface. Supports deep-linked challenge redirects (e.g. `/start daily` returns the challenge description).
* `/help`: Renders a detailed help dashboard.
* `/link <leetcode_username>`: Begins account linking. Generates a temporary code.
* `/verify`: Scans the user's LeetCode profile bio. If the code matches, verifies the account and awards 50 XP/50 coins.
* `/unlink`: Unlinks the user's LeetCode account from the database.
* `/profile`: Displays Level, XP, Coins, and verified LeetCode solved counts, ranking, and contest rating.
* `/streak`: Parses LeetCode submissionCalendar to calculate consecutive active days.
* `/dstreak`: Queries the database to calculate consecutive daily challenges solved.
* `/daily`: Displays the LeetCode Daily Coding Challenge, difficulty, tags, and formatted problem description.
* `/random [difficulty] [tag]`: Finds and displays a random free problem matching the filters.
* `/contest`: Displays the next 4 upcoming LeetCode contests with live countdowns.
* `/solved [slug] [quality]`: Interactively logs a solved problem. If arguments are omitted, fetches recent submissions to let the user select and rate recall (0 to 5).
* `/hint <slug>`: Generates progressive hints (Llama 3.3) rendered via button callback updates.
* `/analyze <code>`: Performs time/space complexity analysis (Llama 3.3) on pasted code or replies.
* `/review <code>`: Performs a structural review (Gemini Flash 2.0) on pasted code or replies.
* `/visualize <code>`: Generates control flow Mermaid flowchart and step-by-step state trace analysis of the code (Llama 3.3). Supports replying to code blocks.
* `/reminders`: Opens an inline menu to toggle Daily Challenge, Streak Warning, and Contest alerts.
* `/leaderboard`: Displays the top 10 users in the current chat ranked by XP.

### Group Moderation & Battle Controls (9)
* `/gleaderboard`: Displays the global top 10 leaderboard by XP.
* `/battle @username` or `/battle open [difficulty] [tag]`: Challenges a user to a 1v1 coding battle, or starts an open multiplayer group battle matching the filters.
* `/stopbattle [uuid]`: Proposes a draw. Opponent can accept or decline. If declined, the proposer can forfeit or keep playing. Admins can use this command to cancel a battle.
* `/pausebattle [uuid]`: Proposes to freeze the battle timer. Pauses the battle if accepted.
* `/resumebattle [uuid]`: Proposes to resume a paused battle. Opponent has 5 minutes to accept, or they forfeit and lose.
* `/myrole`: Displays the user's security role in the current chat.
* `/config_group <setting> <enable/disable>`: Toggles group settings (`battles` or `feed` alerts) (GROUP_ADMIN only).
* `/mute_battle <user> <on/off>`: Mutes/unmutes a member from participating in group battles (GROUP_OWNER only).
* `/clear_group_history`: Resets all leaderboard stats and memberships for the group (GROUP_OWNER only).

### Global Administrative Commands (10)
* `/ping`: Measures Telegram API and Supabase database latency (COORDINATOR only).
* `/stats`: Displays bot usage stats (users, linked accounts, battles, SRS items) (COORDINATOR only).
* `/pban <user> [reason]`: Globally bans a user and blocks all command access (COORDINATOR only).
* `/unpban <user>`: Globally unbans a banned user (COORDINATOR only).
* `/forceverify <user> <leetcode>`: Instantly links and verifies a LeetCode username (COORDINATOR only).
* `/userinfo <user>`: Inspects a user's details: metadata, global role, ban status, and battles (COORDINATOR only).
* `/activebattles`: Lists all active and paused battles in the system (COORDINATOR only).
* `/setrole <user> <COORDINATOR/USER>`: Promotes or demotes a user's role (SUPER_ADMIN only).
* `/maintenance [on/off]`: Toggles global maintenance mode (SUPER_ADMIN only).
* `/broadcast <message>`: Broadcasts a DM message to all registered users (SUPER_ADMIN only).

---

## 9. Project Directory Structure

```
memoize-tgbot/
│
├── database/
│   └── schema.sql                  # Database schema definitions
│
├── src/
│   ├── config.py                   # Environment settings loader (.env)
│   ├── main.py                     # Bot engine & FastAPI health gateway
│   │
│   ├── handlers/                   # Router modules mapping bot commands
│   │   ├── __init__.py             #   └── Router registrations
│   │   ├── admin.py                #   └── Global administrator commands
│   │   ├── ai.py                   #   └── AI hints, analysis, & code review
│   │   ├── common.py               #   └── Account linking, onboarding, profiles
│   │   ├── community.py            #   └── Battles, draws, mutes, group leaderboards
│   │   ├── daily.py                #   └── Daily challenges, contests, random picks
│   │   ├── srs.py                  #   └── Spaced repetition logs & grading
│   │   ├── streaks.py              #   └── Calendar streaks & DCC statistics
│   │   └── visualize.py            #   └── Code flowcharts & variable trace visualization
│   │
│   ├── middlewares/                # Update interceptors
│   │   ├── ban_middleware.py       #   └── Banned user check
│   │   └── maintenance_middleware.py#  └── Maintenance mode blocker
│   │
│   ├── services/                   # Business logic layers
│   │   ├── __init__.py
│   │   ├── leetcode.py             #   └── LeetCode GraphQL Client (httpx)
│   │   ├── supabase_db.py          #   └── Supabase Connection Pool (asyncpg)
│   │   ├── redis_cache.py          #   └── Redis Cache & FSM Manager (redis-py)
│   │   ├── ai_service.py           #   └── Groq & Gemini Flash API Integrations
│   │   └── srs_service.py          #   └── SuperMemo SM-2 Math calculations
│   │
│   └── utils/                      # Internal helpers
│       ├── formatters.py           #   └── HTML descriptions parser & cleaning
│       ├── logging_helper.py       #   └── Administrative activity log channel sender
│       └── roles.py                #   └── Security role resolution
│
├── tests/
│   ├── test_leetcode.py            # LeetCode GraphQL integration tests
│   └── test_leetcode_mock.py       # Offline LeetCode Client mock unit tests
│
├── .gitignore                      # Git ignored files (prevents secrets leakage)
├── Dockerfile                      # Container build manifest
├── Procfile                        # Heroku/Koyeb run command
├── requirements.txt                # Package dependencies
└── runtime.txt                     # Target python version
```

---

## 10. Local Setup, Testing & Deployment

### Local Setup
1. Clone the repository and navigate to the directory:
   ```bash
   git clone https://github.com/Charicific/memoize-tgbot.git
   cd memoize-tgbot
   ```
2. Initialize virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows Powershell
   source .venv/bin/activate  # macOS/Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   SUPABASE_URL=https://your_ref.supabase.co
   SUPABASE_KEY=your_anon_key
   SUPABASE_DB_URL=postgresql+asyncpg://postgres:your_password@db.your_ref.supabase.co:5432/postgres
   REDIS_URL=rediss://default:your_password@your_endpoint.upstash.io:6379
   GROQ_API_KEY=your_groq_key
   GEMINI_API_KEY=your_gemini_key
   PORT=8000
   ```
5. Apply the PostgreSQL schemas using Supabase SQL Editor by executing the queries in [database/schema.sql](database/schema.sql).

### Testing
Verify core LeetCode GraphQL client queries and parsing offline using the mock unit tests:
```bash
pytest tests/test_leetcode_mock.py
```

Alternatively, run integration tests to verify rotating client and proxy implementations against live LeetCode endpoints (set python IO encoding to UTF-8 to prevent encoding errors on Windows console outputs):
```bash
# Windows Powershell
$env:PYTHONIOENCODING="utf-8"
python tests/test_leetcode.py

# macOS/Linux
PYTHONIOENCODING=utf-8 python tests/test_leetcode.py
```

### Running Locally
To launch the bot locally, run the main module:
```bash
python -m src.main
```
*Note: Since `WEBHOOK_URL` is omitted from the local `.env`, the bot automatically runs in **Long Polling** mode for offline debugging.*

### Production Deployment (Koyeb / Docker)
The repository is ready for Koyeb or Docker-based cloud deployments:
* **Docker:** The project includes a [Dockerfile](Dockerfile) that installs requirements, exposes the configuration port, and starts the uvicorn API.
* **Webhooks:** In production, set the environment variable `WEBHOOK_URL` to your deployment domain (e.g. `https://your-app.koyeb.app`) to enable webhook routing for Telegram updates.
* **Keep-Alive:** Setup a free monitor on UptimeRobot pointing to `https://your-app.koyeb.app/health` to keep the container active and receive downtime notifications.
