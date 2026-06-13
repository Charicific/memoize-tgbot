# 🤖 Telegram LeetCode Companion

> **"Duolingo + Anki + Discord + LeetCode — inside Telegram."**

The Telegram LeetCode Companion is a Telegram-native assistant that wraps around LeetCode to make your DSA preparation journey engaging, social, and retention-focused. It integrates spaced repetition scheduling, multiplayer 1v1 coding battles, and AI-powered progressive hints and code reviews.

---

## 🚀 Key Features

### 🧠 Spaced Repetition System (SRS)
* **SM-2 Algorithm Integration:** Logs solved problems and automatically schedules the next review date based on your rated recall quality (0 to 5).
* **Automatic Reminders:** Periodic notifications reminding you of due problem reviews so you never forget optimal approaches.

### ⚔️ Multiplayer Battles & Community
* **1v1 Battles:** Challenge a friend via `/battle @username`. The bot selects a random medium-level problem and tracks who solves and submits it first on LeetCode.
* **Global Leaderboards:** Track XP, levels, and coins on the global scoreboard (`/leaderboard`).

### 🤖 AI Helpers (Groq & Gemini)
* **Progressive Hint Engine (`/hint`):** Generates step-by-step progressive hints (Conceptual $\rightarrow$ Strategic $\rightarrow$ Pseudo-code) using Groq (Llama 3.3 70B) so you solve problems without spoiling the solution.
* **Complexity Analyzer (`/analyze`):** Analyzes the time and space complexity of pasted code.
* **Structural Code Review (`/review`):** Deep code reviews highlighting correctness, edge cases, readability, and improvements using Gemini 2.0 Flash.

### 🎯 Practice & Contests
* **Daily Challenge (`/daily`):** Fetches the active daily coding challenge with a beautifully formatted description.
* **Smart Randomizer (`/random`):** Generates a random free problem, filterable by difficulty and tag (e.g. `/random medium dp`).
* **Contest Schedule (`/contest`):** Lists upcoming contests with direct registration links and timers.

---

## 🛠️ Technology Stack

* **Language:** Python 3.11+
* **Framework:** `aiogram 3.x` (Async-native Telegram Bot API)
* **Database:** Supabase (PostgreSQL) + `asyncpg` (Async Pooler)
* **Cache & Sessions:** Upstash Redis (Serverless TCP/TLS Cache & FSM State Manager)
* **Scheduler:** APScheduler (using persistent PostgreSQL job store)
* **Inference Engines:**
  * **Groq API** (Llama 3.3 70B) for hints and complexity checks.
  * **Gemini API** (Gemini 2.0 Flash) for deep structural code reviews.
* **Hosting:** Koyeb (Free Tier, Docker deployment)
* **Health Check & Webhook:** FastAPI + Uvicorn (lightweight server)

---

## 📂 Project Structure

```
├── database/
│   └── schema.sql                  # Database schema definitions
├── src/
│   ├── config.py                   # Configuration & Env variables
│   ├── main.py                     # Entry point (FastAPI + aiogram)
│   ├── handlers/                   # Command & Callback routers
│   │   ├── common.py               # /start, /help, /link, /verify, /profile
│   │   ├── daily.py                # /daily, /contest, /random
│   │   ├── srs.py                  # /solved rating & callback flows
│   │   ├── ai.py                   # /hint, /analyze, /review
│   │   └── community.py            # /leaderboard, /battle
│   ├── services/                   # Clients & Logic
│   │   ├── leetcode.py             # Custom GraphQL client
│   │   ├── supabase_db.py          # PostgreSQL queries (asyncpg)
│   │   ├── redis_cache.py          # Redis cache & rate limiting
│   │   ├── ai_service.py           # Groq and Gemini clients
│   │   └── srs_service.py          # SM-2 logic & database updates
│   └── utils/
│       └── formatters.py           # Telegram HTML formatting helpers
├── tests/
│   └── test_leetcode.py            # LeetCode integration tests
├── Dockerfile                      # Production container spec
├── Procfile                        # Startup command list
└── runtime.txt                     # Python runtime version
```

---

## ⚙️ Local Setup

### 1. Prerequisites
Ensure you have Python 3.11+ installed. Create and activate a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows Powershell
source .venv/bin/activate  # macOS/Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Database Schema
Execute the queries inside [database/schema.sql](database/schema.sql) in your Supabase SQL editor. Enable RLS (Row Level Security) for security.

### 4. Configure Environment Variables
Create a `.env` file at the root level:
```env
TELEGRAM_BOT_TOKEN=your-bot-token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_DB_URL=postgresql+asyncpg://postgres:password@db-host:5432/postgres
REDIS_URL=rediss://default:password@redis-host:6379
GROQ_API_KEY=your-groq-api-key
GEMINI_API_KEY=your-gemini-api-key
PORT=8000
```
*(Leave `WEBHOOK_URL` blank or commented out to run in local Long Polling mode).*

### 5. Run Tests & Launch
```bash
# Run client tests
python tests/test_leetcode.py

# Start the bot
python -m src.main
```

---

## 🚀 Production Deployment (Koyeb)

1. Push the code to your GitHub repository.
2. Link your repository in Koyeb and create a **Web Service**.
3. Add the environment variables from your `.env` to the service environment.
4. Add the `WEBHOOK_URL` variable in Koyeb set to your app URL (e.g. `https://my-app.koyeb.app`). This switches the bot to Webhook mode automatically.
5. Create a free monitor on **UptimeRobot** pinging `https://my-app.koyeb.app/health` every 5 minutes to prevent the instance from entering sleep mode.
