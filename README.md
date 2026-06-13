<div align="center">

<!-- Animated Header Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,100:6366f1&height=220&section=header&text=LeetCode%20Companion&fontSize=56&fontColor=ffffff&fontAlignY=34&desc=Spaced%20Repetition%20•%201v1%20Battles%20•%20AI%20Coaching%20inside%20Telegram&descAlignY=64&descSize=16&animation=fadeIn" width="100%"/>

<br/>

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-f59e0b?style=for-the-badge&logo=telegram)](https://github.com/aiogram/aiogram)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?style=for-the-badge&logo=supabase)](https://supabase.com)
[![Upstash Redis](https://img.shields.io/badge/Cache-Upstash-DC382D?style=for-the-badge&logo=redis)](https://upstash.com)
[![Koyeb](https://img.shields.io/badge/Deployment-Koyeb-black?style=for-the-badge&logo=docker)](https://koyeb.com)

<br/>

<!-- Tagline -->
> **Meet LeetCode Companion — a Telegram-native assistant that turns your LeetCode prep from a lonely browser grind into a highly retentive, gamified, and social learning habit.**
>
> Meet users where they already live. Spaced repetition retention, competitive multiplayer coding, and instant AI coaching — all right inside Telegram.

<!-- Quick Links -->
[** Features**](#-features) · [**Tech Stack**](#-tech-stack) · [**Architecture**](#-architecture) · [**Quick Start**](#-quick-start) · [**Project Structure**](#-project-structure) · [**License**](#-license)

<br/>

<!-- Separator -->
<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

</div>

## Table of Contents

- [Why LeetCode Companion?](#-why-leetcode-companion)
- [Features](#-features)
  - [Spaced Repetition (SRS) Engine](#-spaced-repetition-srs-engine)
  - [Multiplayer Coding Battles](#-multiplayer-coding-battles)
  - [AI Coaching (Groq + Gemini)](#-ai-coaching-groq--gemini)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Clone the Repository](#clone-the-repository)
  - [Configure Database Schema](#configure-database-schema)
  - [Configure Environment Variables](#configure-environment-variables)
  - [Setup Local Environment & Run](#setup-local-environment--run)
  - [Deployment Command](#deployment-command)
- [Project Structure](#-project-structure)
- [License](#-license)

<br/>

## Why LeetCode Companion?

> *"LeetCode owns the problem sets. This platform owns the learning journey around them."*

Traditional LeetCode practice is isolating, browser-locked, and prone to the **forgetting curve** (where you solve a problem only to completely forget the logic two weeks later). We solve this inside the app you already use every day.

<table>
<td width="50%">

### The Problem
- **The Forgetting Curve:** No review tracking; code is written once and forgotten.
- **Single Player Mode:** Hard to stay accountable or study with friends.
- **Spoiler Hints:** Clicking LeetCode hints spoils the whole approach immediately.
- **High Friction:** Constantly switching tabs to check stats or upcoming contests.

</td>
<td width="50%">

### The Companion Way
- **SM-2 Spaced Repetition:** Calculates recall risk and schedules reviews dynamically.
- **1v1 Group Battles:** Compete against friends in real-time speed coding battles.
- **Progressive Hinting:** Get conceptual, strategic, then pseudo-code hints.
- **Telegram Native:** Instant notifications, inline checks, and stats at your fingertips.

</td>
</table>

<br/>

## Features

### Spaced Repetition (SRS) Engine
* **SM-2 Algorithm Integration:** Logs solved problems and automatically schedules the next review date based on your rated recall quality (0: forgot to 5: perfect).
* **Interactive Button Interface:** Log your recall quality directly via Telegram callback buttons—no manual slug copying required.
* **Daily Reminders:** Database cron checks trigger notifications about due reviews so you never break your retention schedule.

### Multiplayer Coding Battles
* **1v1 Challenges:** Invite any friend via `/battle @username`. The bot selects a random medium-difficulty problem.
* **Real-time Submission Polling:** The bot runs background checks on LeetCode submission history to see who solved it first.
* **Gamified Rewards:** The winner receives 100 XP and 20 coins, while the loser gets 20 XP for competing.
* **Expiration Timers:** Battles automatically expire after 60 minutes if unresolved.

### AI Coaching (Groq + Gemini)
* **Progressive Hints (`/hint`):** Returns hints step-by-step (Conceptual $\rightarrow$ Strategic $\rightarrow$ Pseudo-code) using Groq (Llama 3.3 70B) to help you learn without spoiling solutions.
* **Complexity Analyst (`/analyze`):** Detailed Big-O analysis of your pasted code or in response to a replied code block.
* **Gemini Code Review (`/review`):** Structural code audit assessing correctness, edge cases, readability, and providing optimized alternatives via Gemini 2.0 Flash.

---

## Tech Stack

<div align="center">

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Language** | ![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white) | Core programming language |
| **Bot Framework** | ![aiogram](https://img.shields.io/badge/aiogram-3.x-f59e0b?logo=telegram&logoColor=white) | High-performance asynchronous Telegram API |
| **API Server** | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) | Webhook updates and monitoring endpoints |
| **Database** | ![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?logo=supabase&logoColor=white) | PostgreSQL + direct connections via `asyncpg` |
| **Scheduler** | ![APScheduler](https://img.shields.io/badge/APScheduler-3.x-black) | persistent PG jobstore for cron and battle polling |
| **Cache & Session** | ![Upstash](https://img.shields.io/badge/Upstash_Redis-DC382D?logo=redis&logoColor=white) | Serverless Redis over TCP for FSM state & rate-limiting |
| **Primary AI** | ![Groq](https://img.shields.io/badge/Groq_Llama_3.3-f59e0b) | Ultra-fast progressive hints and complexity analyses |
| **Secondary AI** | ![Gemini](https://img.shields.io/badge/Gemini_2.0_Flash-1A73E8?logo=google-gemini&logoColor=white) | Fallback & deep structural code reviews |
| **Deployment** | ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white) ![Koyeb](https://img.shields.io/badge/Koyeb-000?logo=koyeb&logoColor=white) | Containerized cloud deployment |

</div>

<br/>

## Architecture

```mermaid
graph TB
    subgraph Telegram["Telegram Interface"]
        User["Telegram User"]
        BotAPI["Telegram Bot API"]
    end

    subgraph Backend["Koyeb Container (FastAPI + aiogram)"]
        main["main.py<br/>(FastAPI Server)"]
        dp["Dispatcher / Routers<br/>(aiogram 3)"]
        scheduler["APScheduler<br/>(Async Loop Tasks)"]
        
        subgraph services["Service Modules"]
            lc["LeetCode Client<br/>(httpx + GraphQL)"]
            db_client["Database Helper<br/>(asyncpg Pool)"]
            cache["Redis Cache Manager<br/>(redis-py)"]
            ai["AI Service Manager<br/>(Groq & Gemini)"]
            srs["SRS SM-2 Engine"]
        end
    end

    subgraph Data["Data & State Cloud"]
        Supabase["Supabase DB<br/>(PostgreSQL)"]
        Upstash["Upstash Redis<br/>(FSM States & Limits)"]
    end

    subgraph APIs["AI & External APIs"]
        LeetCode["LeetCode API<br/>(GraphQL)"]
        Groq["Groq API<br/>(Llama 3.3)"]
        Gemini["Gemini API<br/>(Flash 2.0)"]
    end

    User -->|Sends commands| BotAPI
    BotAPI -->|Webhooks / Polling| main
    main --> dp
    dp --> services
    scheduler -->|Poll Active Battles| lc
    scheduler -->|Daily Check due SRS| db_client
    
    lc --> LeetCode
    db_client --> Supabase
    cache --> Upstash
    ai --> Groq
    ai --> Gemini
    srs --> db_client

    style Backend fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#e0e7ff
    style Data fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#d1fae5
    style APIs fill:#1e3a5f,stroke:#38bdf8,stroke-width:2px,color:#e0f2fe
```

<br/>

## Quick Start

### Prerequisites
* **Python** `>= 3.11`
* **Git** installed
* **Supabase** & **Upstash Redis** accounts

### 1. Clone the Repository
```bash
git clone https://github.com/Charicific/memoize-tgbot.git
cd memoize-tgbot
```

### 2. Configure Database Schema
Paste and run the SQL code in [database/schema.sql](database/schema.sql) using your Supabase SQL Editor. We recommend selecting **Run and enable RLS** for baseline table security.

### 3. Configure Environment Variables
Create a `.env` file in the project root:
```env
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

SUPABASE_URL=https://your-ref-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_DB_URL=postgresql+asyncpg://postgres:your-db-password@db.your-ref-id.supabase.co:5432/postgres

REDIS_URL=rediss://default:your-password@your-upstash-endpoint.upstash.io:6379

GROQ_API_KEY=your-groq-api-key
GEMINI_API_KEY=your-gemini-api-key

PORT=8000
```
> **Tip:** Keep the `WEBHOOK_URL` commented out or omitted in local `.env` files to force the bot into **Long Polling** mode for easy offline testing.

### 4. Setup Local Environment & Run
```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows Powershell
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run integration tests
python tests/test_leetcode.py

# Start the application
python -m src.main
```

### 5. Deployment Command
The application is pre-configured with a [Dockerfile](Dockerfile) and [Procfile](Procfile) for deployment to Koyeb or Heroku. In production, configure `WEBHOOK_URL` in the environment settings to enable high-efficiency Telegram webhooks.

---

## Project Structure

```
memoize-tgbot/
│
├── database/
│   └── schema.sql                  # PostgreSQL schemas & tables
│
├── src/
│   ├── config.py                   # App config loading settings from .env
│   ├── main.py                     # App Server startup (FastAPI + aiogram)
│   │
│   ├── handlers/                # Telegram command Handlers
│   │   ├── __init__.py             #   └── Router registrations
│   │   ├── common.py               #   └── /start, /help, /link, /verify, /profile
│   │   ├── daily.py                #   └── /daily, /contest, /random
│   │   ├── srs.py                  #   └── /solved grading & callback flows
│   │   ├── ai.py                   #   └── /hint, /analyze, /review
│   │   └── community.py            #   └── /leaderboard, /battle
│   │
│   └── services/                # Business logic and external clients
│       ├── __init__.py
│       ├── leetcode.py             #   └── LeetCode GraphQL custom API calls
│       ├── supabase_db.py          #   └── supbase direct queries via asyncpg pool
│       ├── redis_cache.py          #   └── Upstash cache operations & FSM storage
│       ├── ai_service.py           #   └── Groq & Gemini Flash API client logic
│       └── srs_service.py          #   └── SM-2 spaced repetition calculator
│
├── tests/
│   └── test_leetcode.py            # Integration query testing scripts
│
├── .gitignore                      # Git ignored files (prevents .env commits)
├── Dockerfile                      # Production Docker container profile
├── Procfile                        # Startup script command
├── requirements.txt                # Package dependencies manifest
└── runtime.txt                     # Target python version
```

---

## License

This project is licensed under a proprietary license. All rights reserved. No part of this codebase may be used, copied, modified, or distributed without explicit written permission from the copyright owner — see the [LICENSE](LICENSE) file for details.

<br/>

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=110&section=footer" width="100%" />

**Built with idea for developers prepping DSA**

</div>
