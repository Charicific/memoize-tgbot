# LeetCode Companion Bot Command & Verification Guide

This guide contains a comprehensive manual of all **37 commands** implemented in the LeetCode Companion bot, categorized by function and permission tier. It provides detailed, simple explanations for each command, along with verification steps.

---

## Command Categories & Reference Manual

### 1. Onboarding & Account Management
These commands help users register, link their LeetCode profiles, check their stats, and verify their access levels.

*   `/start [args]`
    *   **Arguments:** Optional start parameters (e.g. `/start daily`).
    *   **Explanation:** Welcomes new users to the bot with an interactive onboarding card. If started with an argument like `/start daily`, it acts as a quick shortcut to fetch and display the LeetCode daily challenge immediately.
*   `/help`
    *   **Arguments:** None.
    *   **Explanation:** Lists all available commands categorized by user privileges and chat environments, showing brief usage formats.
*   `/link <leetcode_username>`
    *   **Arguments:** Your LeetCode profile username.
    *   **Explanation:** Initiates profile linking. It checks if the username exists and generates a unique verification code (e.g., `LC-4136`) for you to put in your LeetCode public bio.
*   `/verify`
    *   **Arguments:** None.
    *   **Explanation:** Scans your public LeetCode bio for the verification code. Once found, it links your Telegram account to your LeetCode profile, verifies you, and awards you **50 XP and 50 Coins**.
*   `/unlink`
    *   **Arguments:** None.
    *   **Explanation:** Permanently disconnects your linked LeetCode profile from the bot database.
*   `/profile`
    *   **Arguments:** None.
    *   **Explanation:** Displays a beautiful, live dashboard showing your bot level, XP, coins balance, along with real-time public LeetCode statistics (problems solved by difficulty, contest rating, and global ranking).
*   `/myrole`
    *   **Arguments:** None.
    *   **Explanation:** Tells you your currently resolved permission level/role in the chat context where it was run (e.g. USER, GROUP_ADMIN, COORDINATOR, SUPER_ADMIN).

---

### 2. LeetCode Daily & Contests
These commands fetch coding challenges and upcoming contest schedules.

*   `/daily`
    *   **Arguments:** None.
    *   **Explanation:** Fetches and displays the active LeetCode Daily Coding Challenge, presenting its title, difficulty, category tags, a direct link to solve it, and its complete problem description cleanly formatted.
*   `/random [difficulty] [tag]`
    *   **Arguments:** Optional difficulty (`easy`, `medium`, `hard`) and category tag (e.g. `tree`, `dp`).
    *   **Explanation:** Selects a random free problem from LeetCode. If the requested tag-difficulty combination doesn't exist among free problems, it falls back to a random problem of that difficulty.
*   `/contest`
    *   **Arguments:** None.
    *   **Explanation:** Lists the next 4 upcoming LeetCode contests, displaying active registration links and live countdown timers.

---

### 3. Solve Logs & Spaced Repetition System (SRS)
These commands log your practice problems and schedule reviews to reinforce learning.

*   `/solved [slug] [quality]`
    *   **Arguments:** Optional problem slug and recall score (0 to 5).
    *   **Explanation:** Logs a solved problem to the Spaced Repetition system. If arguments are omitted, it displays an interactive list of your latest 5 accepted LeetCode submissions. Selecting a problem lets you grade your recall (from 0 - Forgot to 5 - Perfect), which calculates your next review date using the SuperMemo SM-2 algorithm.
    *   **Note:** The system filters out problems you haven't solved yet. If you try to log a problem you haven't solved on LeetCode (not in your database history or not in your last 20 accepted submissions), you will receive a warning telling you to re-submit on LeetCode first.
*   `/solve <query>`
    *   **Arguments:** Problem ID, slug, or title (e.g. `1`, `two-sum`, `two sum`).
    *   **Explanation:** Looks up details for any LeetCode problem, presenting difficulty, tags, a clean description snippet, and direct buttons to solve on LeetCode. Displays up to 5 suggestion buttons if the query is ambiguous.
*   `/reviews`
    *   **Arguments:** None.
    *   **Explanation:** Displays your active Spaced Repetition reviews queue (split into Due and Upcoming items) and provides inline buttons to instantly master and archive due items.
*   `/rm_srs <query>`
    *   **Arguments:** Problem ID, slug, or title.
    *   **Explanation:** Removes a problem from your active Spaced Repetition reviews queue. Displays up to 5 choice buttons if ambiguous.

---

### 4. Coding Streaks
Track consistency and daily goals.

*   `/streak`
    *   **Arguments:** None.
    *   **Explanation:** Queries LeetCode's calendar API to calculate your active consecutive calendar days coding streak, showing current streak, longest streak, and total active days.
*   `/dstreak`
    *   **Arguments:** None.
    *   **Explanation:** Calculates your consecutive Daily Challenge solve streak recorded in the bot's local database.

---

### 5. AI Coding Assistants
Use AI (Gemini and Llama models) to learn, analyze, and review code.

*   `/hint <problem_slug>`
    *   **Arguments:** The slug of the LeetCode problem.
    *   **Explanation:** Generates progressive step-by-step hints. It starts with Hint 1 (conceptual). You can click inline buttons to reveal Hint 2 (strategic approach) and Hint 3 (pseudo-code).
*   `/analyze <code_block>`
    *   **Arguments:** A pasted block of code (or replied message containing code).
    *   **Explanation:** Analyzes code for Big-O time and space complexities using AI.
*   `/review <code_block>`
    *   **Arguments:** A pasted block of code (or replied message containing code).
    *   **Explanation:** Audits code for edge cases, logic bugs, efficiency, and optimization recommendations.
*   `/visualize <code_block>`
    *   **Arguments:** A pasted block of code (or replied message containing code).
    *   **Explanation:** Converts code into a visual Mermaid flowchart image and outputs a step-by-step state trace analysis of how variables mutate.

---

### 6. Settings & Reminders
Manage notification preferences.

*   `/reminders`
    *   **Arguments:** None.
    *   **Explanation:** Opens a private menu with toggles for **Daily Challenge Alerts**, evening **Streak Warnings** (notifies you if you haven't solved today), and **Contest Alerts**.

---

### 7. Leaderboards
Rank and compare users by experience points.

*   `/leaderboard`
    *   **Arguments:** None.
    *   **Explanation:** Shows the top 10 users ranked by XP. Group-exclusive in group chats, and global in private DMs.
*   `/gleaderboard`
    *   **Arguments:** None.
    *   **Explanation:** Displays the global top 10 leaderboard by XP (accessible in both groups and DMs).

---

### 8. Group Battles
Interactive multiplayer coding matches.

*   `/battle <args>`
    *   **Arguments:** Target user (e.g. `@opponent`) or `open [difficulty] [tag]` (multiplayer lobby).
    *   **Explanation:** Launches a 60-minute coding battle. If sent as a 1v1 challenge in private DMs, it routes directly to the opponent's DM. If starting an open battle in a group, it displays a lobby where players can click `Join Battle` and the host/admin starts it.
*   `/stopbattle [battle_uuid]`
    *   **Arguments:** Optional active battle UUID.
    *   **Explanation:** Proposes a draw in 1v1 battles. If declined, the proposer can forfeit (opponent wins) or keep playing. In group battles, the host or admins can use this command to cancel the battle instantly.
*   `/pausebattle [battle_uuid]`
    *   **Arguments:** Optional active battle UUID.
    *   **Explanation:** Proposes to freeze the battle timer. Pauses the battle if the opponent accepts (1v1) or immediately when run by the host/admin (group battles).
*   `/resumebattle [battle_uuid]`
    *   **Arguments:** Optional active battle UUID.
    *   **Explanation:** Proposes to unfreeze the battle timer. Opponent has 5 minutes to accept (1v1) or they forfeit and lose. Runs immediately when run by the host/admin (group battles).

---

### 9. Group Moderation
Manage bot configurations in group environments.

*   `/config_group <setting> <value>`
    *   **Arguments:** Setting name (`battles` or `feed`) and value (`enable` or `disable`).
    *   **Explanation:** Restricts group bot actions. E.g. `/config_group battles disable` prevents battles in the group. Requires `GROUP_ADMIN` or higher.
*   `/mute_battle <@username> <on/off>`
    *   **Arguments:** Target member username and mute state.
    *   **Explanation:** Blocks or unblocks a specific member from participating in group battles. Requires `GROUP_OWNER` or higher.
*   `/clear_group_history`
    *   **Arguments:** None.
    *   **Explanation:** Wipes all local leaderboard statistics and scores for the current group. Requires `GROUP_OWNER` or higher.

---

### 10. Global System Metrics & Stats
Diagnostic and monitoring tools for system coordinators.

*   `/ping`
    *   **Arguments:** None.
    *   **Explanation:** Measures the bot's API response time, database query latency, and total uptime from the last restart. Requires `COORDINATOR` or higher.
*   `/stats`
    *   **Arguments:** None.
    *   **Explanation:** Displays global system usage statistics (registered users, linked/verified counts, active/completed battles, active SRS reviews, community counts of active groups and member channels, and count of distinct users with reminders enabled). Requires `COORDINATOR` or higher.
*   `/activebattles`
    *   **Arguments:** None.
    *   **Explanation:** Lists all active and paused battles currently running in the database. Requires `COORDINATOR` or higher.
*   `/userinfo <@username_or_telegram_id>`
    *   **Arguments:** Target user identifier.
    *   **Explanation:** Retrieves a user profile summary showing their linked account status, resolved role, ban status, level/XP stats, and active battles. Requires `COORDINATOR` or higher.

---

### 11. Global Moderation & Verification
Account overrides and global suspensions.

*   `/pban <@username_or_telegram_id> [reason]`
    *   **Arguments:** Target user identifier and optional reason.
    *   **Explanation:** Globally bans a user from interacting with the bot. The ban state is cached in Redis, instantly blocking command execution. Requires `COORDINATOR` or higher.
*   `/unpban <@username_or_telegram_id>`
    *   **Arguments:** Target user identifier.
    *   **Explanation:** Restores a banned user's bot access. Requires `COORDINATOR` or higher.
*   `/forceverify <@username_or_telegram_id> <leetcode_username>`
    *   **Arguments:** Target user and their LeetCode profile username.
    *   **Explanation:** Bypasses standard bio checks to manually link and verify a user's profile. Requires `COORDINATOR` or higher.

---

### 12. Super Admin System Controls
Global deployment overrides.

*   `/setrole <@username_or_telegram_id> <COORDINATOR/USER>`
    *   **Arguments:** Target user and target role.
    *   **Explanation:** Promotes or demotes a user's bot privilege level, invalidating their role cache immediately. Requires `SUPER_ADMIN` only.
*   `/maintenance [on/off]`
    *   **Arguments:** Optional toggle state.
    *   **Explanation:** Toggles global maintenance mode. When enabled, regular users are blocked from running commands. Requires `SUPER_ADMIN` only.
*   `/pbroadcast <message>`
    *   **Arguments:** Broadcast text (supports HTML tags).
    *   **Explanation:** Broadcasts message to all users' private DMs at a safe rate limit of 30 messages/second. Sends a detailed failure report `.txt` file (with type, name, and username of failed chats) to super admins. Requires `SUPER_ADMIN` only.
*   `/gbroadcast <message>`
    *   **Arguments:** Broadcast text (supports HTML tags).
    *   **Explanation:** Broadcasts message to all active groups. Sends a detailed failure report `.txt` file to super admins. Requires `SUPER_ADMIN` only.
*   `/cbroadcast <message>`
    *   **Arguments:** Broadcast text (supports HTML tags).
    *   **Explanation:** Broadcasts message to all tracked channels. Sends a detailed failure report `.txt` file to super admins. Requires `SUPER_ADMIN` only.
*   `/broadcast <message>`
    *   **Arguments:** Broadcast text (supports HTML tags).
    *   **Explanation:** Universally broadcasts message to all private DMs, active groups, and tracked channels. Sends a detailed failure report `.txt` file to super admins. Requires `SUPER_ADMIN` only.

---

## Step-by-Step Verification Guide

Follow this logical path to verify the full bot logic:

### 1. Onboarding, Linking & Reminders (Private DM)
*   **Action:** Send `/start` to the bot.
    *   *Expected:* Welcome card with onboarding instructions.
*   **Action:** Send `/link <leetcode_username>` (e.g., `/link ez_manish`).
    *   *Expected:* Bot confirms receipt and prints a verification code (e.g., `LC-4136`).
*   **Action:** Put the code in your LeetCode profile bio and send `/verify`.
    *   *Expected:* Bio verification succeeds, awarding **50 XP** and **50 Coins**.
*   **Action:** Send `/profile` and `/myrole`.
    *   *Expected:* Dashboard displaying level, XP, coins, verified LeetCode stats, and role `USER`.
*   **Action:** Send `/reminders`.
    *   *Expected:* Interactive menu showing toggles for **Daily Challenge**, **Streak Warning**, and **Contest Alerts**.
*   **Action:** Click a toggle button (e.g., `Streak Warning: ON`).
    *   *Expected:* Button status flips, updates the database, and shows a callback alert confirmation. Click `Save & Close` to save.
*   **Action:** Send any of these commands using a dot `.` prefix instead of a slash `/` (e.g. `.ping`, `.profile`, `.reminders`).
    *   *Expected:* The middleware interceptor rewrites the prefix and parses standard command entities, causing the command to run identically to its slash equivalent.

### 2. LeetCode Problems, AI, and Streaks
*   **Action:** Send `/daily`, `/random easy two-pointers`, and `/contest`.
    *   *Expected:* Correct problem/contest cards are fetched and rendered with interactive links.
*   **Action:** Send `/streak` and `/dstreak`.
    *   *Expected:* `/streak` parses LeetCode submissionCalendar calendar to return active days. `/dstreak` calculates consecutive days solved from local challenge logs.
*   **Action:** Send `/hint two-sum`.
    *   *Expected:* Renders Hint 1 (Conceptual) with a button `Get Hint 2`. Clicking details Hint 2 (Strategic), which adds a button `Get Hint 3`. Hint 3 (Detailed Pseudo-code) completes the flow.
*   **Action:** Send `/analyze` (or reply to a code block with `/analyze`).
    *   *Expected:* Time/space Big-O analysis from Groq Llama 3.3.
*   **Action:** Send `/review` (or reply to a code block with `/review`).
    *   *Expected:* Complete code auditing and code quality recommendations from Gemini Flash 2.0.
*   **Action:** Send `/visualize <code>` (or reply to a code block with `/visualize`).
    *   *Expected:* Bot generates a Mermaid flowchart via Groq (Llama 3.3), encodes and renders it via `mermaid.ink` as a photo, and replies with a detailed step-by-step trace explanation of variables.
*   **Action:** Send `/solve 1` or `/solve two-sum`.
    *   *Expected:* Bot retrieves and renders the details card for *Two Sum* with direct solve links.
*   **Action:** Send `/solve sum`.
    *   *Expected:* Bot displays up to 5 ambiguous matches as buttons. Clicking one updates the card to the selected problem's details.

### 3. Spaced Repetition System (SRS)
*   **Action:** Send `/solved`.
    *   *Expected:* List of the 5 most recent accepted LeetCode submissions fetched dynamically.
*   **Action:** Click on a problem button.
    *   *Expected:* Prompts with grading callback buttons (0 - Forgot to 5 - Perfect).
*   **Action:** Click a grading option (e.g., `4 - Easy`).
    *   *Expected:* Database records review, calculates next date using SuperMemo SM-2, logs parameters (interval, ease factor), and awards 15 XP & 5 coins.
*   **Action:** Send `/solved 1 4` for a problem you haven't solved on LeetCode.
    *   *Expected:* Bot rejects the log and displays a warning to solve it on LeetCode first.
*   **Action:** Send `/reviews`.
    *   *Expected:* Bot returns your active review queue with `✅ Master` buttons. Clicking a button masters the item, pops it from the queue, and updates the message.
*   **Action:** Send `/rm_srs 1` or `/rm_srs two-sum`.
    *   *Expected:* Bot confirms manual deletion of *Two Sum* from your review queue.

### 4. Multiplayer Coding Battles (Group Chat / DM)
*   **Action:** In a group, send `/battle @opponent_username`.
    *   *Expected:* Invitation card appears with `Accept` and `Decline` buttons.
*   **Action:** In a private DM, send `/battle @opponent_username`.
    *   *Expected:* Invitation card is sent directly to the opponent's DM. The challenger receives a confirmation card.
*   **Action:** Opponent clicks `Accept`.
    *   *Expected:* Starts a 60-minute active battle, cancels other pending challenges for both players, and lists the problem link.
*   **Action:** In a group, send `/battle open` (or `/battle open easy arrays`).
    *   *Expected:* Open battle lobby card is created showing problem title, difficulty, and lists joined participants. Inside are inline buttons for `🎮 Join Battle` and `🏁 Start Battle`.
*   **Action:** Other group members click `🎮 Join Battle`.
    *   *Expected:* Bot updates the lobby message dynamically, listing the new participants.
*   **Action:** Battle creator clicks `🏁 Start Battle`.
    *   *Expected:* Entry pool is locked, the battle status changes to `ACTIVE` with a 60-minute deadline, and the problem link is sent to the group.
*   **Action:** Propose a pause using `/pausebattle`.
    *   *Expected:* Pause prompt shows up. Opponent clicks `Accept Pause`. Battle status becomes `PAUSED` and the timer freezes.
*   **Action:** Propose to resume using `/resumebattle`.
    *   *Expected:* Resume prompt appears. Opponent has 5 minutes to accept. If they fail to click `Accept Resume` within 5 minutes, they forfeit, and the proposer is declared the winner (awarded 100 XP & 20 coins).
*   **Action:** Propose a draw using `/stopbattle`.
    *   *Expected:* Draw prompt appears. Opponent clicks `Decline Draw`. Prompt changes to ask proposer to Forfeit or Keep Playing. Clicking `Forfeit` awards opponent the win.
*   **Action:** Complete a battle by solving the problem on LeetCode.
    *   *Expected:* The scheduler detects the solve, updates battle/participant status, notifies the group of the solve timing, and compiles a final ranking leaderboard once everyone has solved or the 60-minute limit is reached. Rewards are distributed tier-wise (1st: 150 XP/30 coins, 2nd: 100 XP/20 coins, 3rd: 75 XP/15 coins, others who solved: 50 XP/10 coins, unsolved: 10 XP/0 coins).

### 5. Group-Specific Administration
*   **Action:** Send `/config_group battles disable` as a group admin.
    *   *Expected:* Confirms setting disabled. Trying to run `/battle` yields an error message.
*   **Action:** Send `/mute_battle @member_username on` as the group owner.
    *   *Expected:* Member is blocked from initiating or accepting battles in the group.
*   **Action:** Send `/clear_group_history` as the group owner.
    *   *Expected:* Group leaderboard stats reset to zero.

### 6. Global Administration & Security
*   **Action:** Send `/ping` and `/stats` as a coordinator/admin.
    *   *Expected:* Latency metrics (API & Database) and global system usage statistics are returned.
*   **Action:** Send `/userinfo @user_username` as coordinator.
    *   *Expected:* Detailed inspection summary of roles, ban status, and stats.
*   **Action:** Send `/pban @user_username "Spamming"` as coordinator.
    *   *Expected:* User is globally banned, cached in Redis, sent a ban notification, and blocked from all bot commands.
*   **Action:** Send `/maintenance on` as a super admin.
    *   *Expected:* Global maintenance mode enabled. Regular users trying to interact with the bot receive a block notice.
*   **Action:** Send `/pbroadcast Update` or `/broadcast System Broadcast` as super admin.
    *   *Expected:* Broadcast runs asynchronously, and DMs super admins a detailed `.txt` failure report containing the type, name, and username of any failed chats.
*   **Action:** Trigger an unhandled exception or system error.
    *   *Expected:* The private log channel receives a compact one-liner notification message, with the full traceback and update details attached directly to the same message as an `error_details.txt` file.

### 7. Conversational Fallback & Topic Navigation
* **Action**: In private DM, send a greeting like `"hello"` or `"hi Memoize"`.
  * **Expected**: Bot replies with a friendly greeting detailing its features, accompanied by a balanced 2x3 topic navigation inline keyboard (including `"🔗 Link Profile"`).
* **Action**: Send a message with a specific topic keyword like `"tell me about coding battles"` or `"how do I connect my profile?"`.
  * **Expected**: Bot matches the keyword and replies with the relevant guide (Battles Guide / Link Profile), setting the topic context in cache.
* **Action**: Send a follow-up query containing `"how do I play?"` or `"verification failing, troubleshoot please"`.
  * **Expected**: Bot checks the active context (e.g., `"battles"` or `"link"`) and replies with specific follow-up instructions (e.g. Battle Startup Steps / Link Verification Troubleshooting).
* **Action**: Send sentiment-expressing text like `"thank you so much!"` or `"bye bye!"`.
  * **Expected**: Bot responds with a friendly rule-based reply (gratitude or goodbye farewell) and resets active context.
* **Action**: Send any text that does not match any keywords (e.g. `"xyz abc"`).
  * **Expected**: Bot replies with a clean fallback message ("I didn't quite catch that...") along with the interactive 2x3 inline menu.
* **Action**: Click on an inline button (e.g. `"🔗 Link Profile"`).
  * **Expected**: Bot edits the message text dynamically to show the LeetCode Account Linking & Verification guide while keeping the inline navigation keyboard.

---

## Verification Troubleshooting

*   **IPv6 Supabase Connections:** If database queries hang or timeout locally, ensure you are running Cloudflare WARP or a similar VPN supporting IPv6 database endpoints.
*   **Long Polling vs Webhooks:** For local testing, keep the `WEBHOOK_URL` commented out in `.env` to fall back to Long Polling. Ensure the production webhook is properly registered using `WEBHOOK_URL` and `WEBHOOK_PATH`.
