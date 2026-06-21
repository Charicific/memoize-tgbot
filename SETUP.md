# LeetCode Companion Bot Setup & Deployment Guide

This guide details the steps to configure, test, and deploy the Telegram LeetCode Companion bot.

---

## Step 1: Initialize the Database (Supabase)

1. Go to [Supabase](https://supabase.com) and create a new project (free tier).
2. Once the database is ready, navigate to the **SQL Editor** in the Supabase dashboard.
3. Paste the contents of [database/schema.sql](database/schema.sql) and run it to create your database tables (`users`, `linked_accounts`, `problem_history`, `srs_reviews`, and `battles`).
4. Copy the connection details from **Project Settings** > **Database**:
   * Copy the **Connection Pooler URL** (Transaction mode, port 5432/6543) for the `SUPABASE_DB_URL` environment variable.
   * **Important:** Prefix the pooler URL with `postgresql+asyncpg://` instead of `postgres://` or `postgresql://` in your config to support asynchronous calls in Python.

---

## Step 2: Setup Cache (Upstash Redis)

1. Go to [Upstash](https://upstash.com) and create a free serverless Redis database.
2. In the database details dashboard, copy the **Redis Connect URL** (under the Node.js/Python or raw TCP format, starting with `rediss://`).

---

## Step 3: Get AI API Keys

1. **Groq API Key:** Register on [Groq Console](https://console.groq.com) and create a free API Key. This is used for progressive hints and complexity analysis.
2. **Gemini API Key:** Register on [Google AI Studio](https://aistudio.google.com) and generate a free API Key. This is used for structural code reviews.

---

## Step 4: Create your Telegram Bot

1. Open Telegram and search for the user `@BotFather`.
2. Send the command `/newbot` and follow the steps to name your bot and choose a username.
3. Copy the **HTTP API Bot Token** provided.

---

## Step 5: Configure Environment Variables

Create a file named `.env` at the root of your project directory (`.env`) and populate it with your credentials:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_DB_URL=postgresql+asyncpg://postgres.your-project-ref:your-db-password@aws-0-region.pooler.supabase.com:6543/postgres
REDIS_URL=rediss://default:your-redis-password@your-redis-endpoint.upstash.io:6379
GROQ_API_KEY=gsk_your_groq_api_key
GEMINI_API_KEY=AIzaSyYourGeminiApiKey
PORT=8000
UPTIMEROBOT_API_KEY=ur123456-abcdef
UPTIMEROBOT_MONITOR_ID=777777777
```

> [!NOTE]
> Keep `WEBHOOK_URL` blank (or omitted) in your local `.env`. When this is omitted, the bot will automatically run in **Long Polling** mode, which is ideal for local debugging.

---

## Step 6: Test & Run Locally

1. **Activate the Virtual Environment:**
   ```powershell
   .venv\Scripts\activate
   ```
2. **Run the integration test:**
   Confirm connection to LeetCode's GraphQL API by fetching the daily challenge and profiles:
   ```bash
   python tests/test_leetcode.py
   ```
3. **Start the main application:**
   ```bash
   python -m src.main
   ```
4. **Interact with the Bot:**
   * Open Telegram, find your bot, and send `/start`.
   * Link your LeetCode account: `/link <username>`.
   * Add the generated verification code (e.g. `LC-1234`) to your LeetCode bio and send `/verify`.
   * Run `/daily`, `/contest`, or `/random` to fetch challenges.
   * Grade a solution: `/solved` (displays interactive buttons for recall scoring).

---

## Step 7: Production Deployment (Koyeb)

1. Push your repository to **GitHub**.
2. Create an account on [Koyeb](https://www.koyeb.com).
3. Connect your GitHub repository to Koyeb.
4. Set the **Service Type** to **Web Service**.
5. Add the exact same environment variables from your `.env` to the Koyeb Environment Variables settings.
6. Add one additional environment variable in Koyeb:
   * `WEBHOOK_URL`: `https://[your-koyeb-app-name].koyeb.app` (replaces polling with high-performance webhook delivery).
7. In the **Ports** section, set port `8000` with protocol `HTTP` and **leave the Path field empty** (do not fill in `/health` or any path — an empty path exposes all routes publicly, which is required for the `/webhook` endpoint to work).
8. Koyeb will automatically detect the [Dockerfile](Dockerfile) or [Procfile](Procfile), build, and launch your bot in webhook mode.

---

## Step 8: Setup Keep-Alive (UptimeRobot)

1. Go to [UptimeRobot](https://uptimerobot.com) and create a free account.
2. Setup a **HTTPS Monitor**:
   * **URL:** `https://[your-koyeb-app-name].koyeb.app/health`
   * **Interval:** Every 5 minutes.
3. This keeps the free instance active, prevents sleep behaviors, and notifies you immediately if the service goes offline.
