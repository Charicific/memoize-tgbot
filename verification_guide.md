# LeetCode Companion Bot Command & Verification Guide

This guide contains a comprehensive checklist of the bot's commands, how to trigger them on Telegram, and what expected outcomes you should look for during verification.

---

## Commands Quick Reference

Here is a summary of all commands registered in `@MemoizeLC_bot`:

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/start` | None | Welcome message and entry onboarding |
| `/help` | None | Lists all available commands with details |
| `/link` | `<leetcode_username>` | Links your LeetCode profile (generates a verification code) |
| `/verify` | None | Checks your LeetCode profile bio for the code to confirm ownership |
| `/profile` | None | Displays your Level, XP, Coins, and LeetCode stats dashboard |
| `/daily` | None | Fetches the LeetCode "Daily Coding Challenge" (safely truncated) |
| `/random` | `[difficulty]` `[tag]` | Picks a random free LeetCode problem (e.g., `/random easy tree`) |
| `/contest` | None | Lists upcoming contests with start time countdowns |
| `/solved` | `[problem_slug]` `[quality]` | Logs a solved problem and schedules review (quality 0 to 5) |
| `/hint` | `<problem_slug>` | Generates progressive AI hints (Groq - Llama 3.3) |
| `/analyze` | `<paste_code>` | Analyzes code for time and space complexities (Groq - Llama 3.3) |
| `/review` | `<paste_code>` | Performs a structural code quality review (Gemini Flash 2.0) |
| `/leaderboard`| None | Shows the top 10 users ranked by XP |
| `/battle` | `@username` | Challenges another registered user to a timed 1v1 coding battle |

---

## Step-by-Step Verification Guide

Follow this logical path to verify the full bot logic:

### 1. Onboarding & Linking (Account Setup)
* **Action**: In Telegram, send `/start`.
  * **Expected Output**: A welcoming onboarding card with quick steps on how to link your LeetCode profile.
* **Action**: Send `/link <your_leetcode_username>` (e.g., `/link Ez_Manish`).
  * **Expected Output**: Bot replies that the request is received and provides a unique verification code (e.g., `LC-4136`).
* **Action**: Update your LeetCode profile "Read Me" or "About Me" section with the code.
* **Action**: Send `/verify`.
  * **Expected Output**: The bot scans your LeetCode bio, validates the code, rewards you with **50 XP** and **50 Coins**, and displays a success notification!
* **Action**: Send `/profile`.
  * **Expected Output**: A profile dashboard showing your level, coins, XP, and live LeetCode stats (Easy/Medium/Hard solved count and Contest Rating).

### 2. LeetCode Problems & Scheduling
* **Action**: Send `/daily`.
  * **Expected Output**: Displays today's Daily Coding Challenge with a description snippet, topic tags, difficulty, and a direct link to solve.
* **Action**: Send `/random medium dp` (or similar difficulty/tag combinations).
  * **Expected Output**: Finds and posts a random free problem matching your filters.
* **Action**: Send `/contest`.
  * **Expected Output**: Shows the next 4 upcoming LeetCode contests with active countdown timers.

### 3. Spaced Repetition System (SRS)
* **Action**: Send `/solved`.
  * **Expected Output**: An interactive button menu showing your 5 most recent accepted submissions from LeetCode.
* **Action**: Click one of the problem buttons.
  * **Expected Output**: Replaces the menu with recall rating buttons (0 to 5).
* **Action**: Click a rating (e.g., `4 - Easy`).
  * **Expected Output**: Logs the review to the database, recalculates the next review date using the SuperMemo SM-2 algorithm, and displays your updated scheduling parameters.

### 4. AI-Powered Assistant
* **Action**: Send `/hint two-sum` (or any other valid problem slug).
  * **Expected Output**: The bot generates progressive conceptual, strategic, and pseudocode hints using Groq's Llama 3.3 model.
* **Action**: Send `/analyze` followed by a block of code (e.g., a Two Sum solution).
  * **Expected Output**: A detailed analysis of time and space complexity with suggestions on how to improve efficiency.
* **Action**: Send `/review` followed by a block of code.
  * **Expected Output**: A deep structural review powered by Gemini Flash 2.0 highlighting syntax optimization, readability tips, and code improvements.

### 5. Community & Competitions
* **Action**: Send `/leaderboard`.
  * **Expected Output**: Displays a list of the top 10 users ranked by accumulated XP.
* **Action**: Send `/battle @friend_username` (Note: both users must be registered).
  * **Expected Output**: Sends an active 1v1 battle challenge with standard ` Accept` and `Decline` buttons. If accepted, the battle starts a 60-minute countdown, and the bot automatically polls both players' submissions to award the winner.

---

## Verification Troubleshooting

* **Unsupported Tag Error**: If you see formatting issues, verify that you are escaping angle brackets or tags in your custom inputs.
* **Database Offline**: If the bot is not responding, make sure your Cloudflare WARP client is running (to support IPv6 connectivity to Supabase) and check the status of the local server process.
