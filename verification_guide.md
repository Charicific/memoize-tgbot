# LeetCode Companion Bot Command & Verification Guide

This guide contains a comprehensive checklist of all **37 commands** implemented in the LeetCode Companion bot, how to trigger them, and what expected outcomes you should look for during verification.

---

## Commands Quick Reference

### 1. General User Commands

These commands are available to all users in private DMs and groups.

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/start` | `[args]` | Welcome onboarding message. Start args like `/start daily` auto-fetches the daily challenge. |
| `/help` | None | Lists all available commands with usage details. |
| `/link` | `<leetcode_username>` | Initiates linking by generating a unique verification code (e.g., `LC-1234`). |
| `/verify` | None | Scans your LeetCode profile bio for the verification code to complete account linking (awards 50 XP & 50 coins). |
| `/unlink` | None | Unlinks your LeetCode profile from the bot database. |
| `/profile` | None | Displays your Level, XP, Coins, and live LeetCode statistics dashboard (solved counts, global rank, contest rating). |
| `/streak` | None | Displays your consecutive calendar days coding streak from your LeetCode profile calendar. |
| `/dstreak` | None | Displays your consecutive Daily Challenge solve streak recorded in the bot's database. |
| `/daily` | None | Fetches the LeetCode Daily Coding Challenge with difficulty, tags, link, and full problem description. |
| `/random` | `[difficulty] [tag]` | Picks a random free LeetCode problem (e.g., `/random medium slidingwindow`). |
| `/contest` | None | Lists the next 4 upcoming LeetCode contests with active countdowns and registration links. |
| `/solved` | `[slug] [quality]` | Logs a solved problem. If arguments are omitted, launches an interactive menu of your recent 5 LeetCode solves to rate recall (0 to 5) and schedule reviews. |
| `/hint` | `<problem_slug>` | Generates progressive AI hints (Groq Llama 3.3) step-by-step (Hint 1: Conceptual, Hint 2: Strategic, Hint 3: Pseudo-code). |
| `/analyze` | `<paste_code>` | Analyzes a pasted code block (or replied message) for Big-O time and space complexities. |
| `/review` | `<paste_code>` | Performs a structural review of a code block (or replied message) for correctness and optimization via Gemini Flash 2.0. |
| `/visualize` | `<paste_code>` | Generates a control flow Mermaid flowchart image and a step-by-step state trace analysis of a code block or reply. |
| `/reminders` | None | Opens an interactive menu in DMs to toggle daily challenge alerts, evening streak warnings, and contest alerts. |
| `/leaderboard` | None | Shows the top 10 users ranked by XP (group-exclusive in groups, global in private chat). |

### 2. Group Moderation & Battle Controls

These commands are contextual to group environments and active multiplayer battles.

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/gleaderboard`| None | Shows the global top 10 leaderboard by XP (available in both groups and DMs). |
| `/battle` | `@username` or `open [difficulty] [tag]` | Challenges a verified user to a 60-minute 1v1 coding battle, or starts an open multiplayer group battle. |
| `/myrole` | None | Displays your resolved role and privileges in the current chat context. |
| `/stopbattle` | `[battle_uuid]` | Proposes a draw agreement to your opponent. If accepted, the battle ends. If declined, you can forfeit (giving opponent the win) or keep playing. Admins can use this to forcefully cancel a battle. |
| `/pausebattle`| `[battle_uuid]` | Proposes to freeze/pause the battle timer. Requires opponent agreement or admin override. |
| `/resumebattle`| `[battle_uuid]` | Proposes to resume a paused battle. Opponent has 5 minutes to accept, or they forfeit and lose. Admins can override to resume instantly. |
| `/config_group`| `<setting> <val>` | Configure group settings: `battles [enable/disable]` or `feed [enable/disable]` (GROUP_ADMIN only). |
| `/mute_battle`| `<user> <on/off>` | Mutes or unmutes a member from participating in group battles (GROUP_OWNER only). |
| `/clear_group_history`| None | Resets all leaderboard statistics and scores for this group (GROUP_OWNER only). |

### 3. Global Administrative Commands

These commands require administrative authorization (`COORDINATOR` or `SUPER_ADMIN`).

| Command | Arguments | Required Role | Description |
| :--- | :--- | :--- | :--- |
| `/ping` | None | COORDINATOR | Measures Telegram Bot API and Supabase database latency metrics. |
| `/stats` | None | COORDINATOR | Displays global bot usage stats (total users, verified profiles, active/completed battles, and SRS items). |
| `/pban` | `<user> [reason]` | COORDINATOR | Globally bans a user and blocks all bot commands. |
| `/unpban` | `<user>` | COORDINATOR | Globally unbans a banned user and restores access. |
| `/forceverify`| `<user> <leetcode>`| COORDINATOR | Bypasses bio verification checks to manually link and verify a user's LeetCode profile. |
| `/userinfo` | `<user>` | COORDINATOR | Inspects user metadata: resolved roles, ban status, linked profile, levels, XP, and active battles. |
| `/activebattles`| None | COORDINATOR | Lists all active and paused battles currently running in the system. |
| `/setrole` | `<user> <role>` | SUPER_ADMIN | Promotes or demotes a user to `COORDINATOR` or `USER`. |
| `/maintenance`| `[on/off]` | SUPER_ADMIN | Toggles global maintenance mode (blocks regular users). |
| `/broadcast` | `<message>` | SUPER_ADMIN | Broadcasts a HTML message to all registered users in private DMs. |

---

## Dynamic Role Hierarchy

The bot evaluates user access using five dynamic roles (highest to lowest):
1. **SUPER_ADMIN**: Defined statically in settings `.env` (`super_admin_ids`). Complete command override.
2. **COORDINATOR**: Stored in the database `users.role = 'COORDINATOR'`. Access to global admin/moderation tools.
3. **GROUP_OWNER**: Dynamically resolved as the creator of the current group. Access to group resets and mutes.
4. **GROUP_ADMIN**: Dynamically resolved as a group administrator in the current group. Access to group settings.
5. **USER**: Default role for any registered user/member.

---

## Step-by-Step Verification Guide

Follow this logical path to verify the full bot logic:

### 1. Onboarding, Linking & Reminders (Private DM)
* **Action**: Send `/start` to the bot.
  * **Expected**: Welcome card with onboarding instructions.
* **Action**: Send `/link <leetcode_username>` (e.g., `/link ez_manish`).
  * **Expected**: Bot confirms receipt and prints a verification code (e.g., `LC-4136`).
* **Action**: Put the code in your LeetCode profile bio and send `/verify`.
  * **Expected**: Bio verification succeeds, awarding **50 XP** and **50 Coins**.
* **Action**: Send `/profile` and `/myrole`.
  * **Expected**: Dashboard displaying level, XP, coins, verified LeetCode stats, and role `USER`.
* **Action**: Send `/reminders`.
  * **Expected**: Interactive menu showing toggles for **Daily Challenge**, **Streak Warning**, and **Contest Alerts**.
* **Action**: Click a toggle button (e.g., `Streak Warning: ON`).
  * **Expected**: Button status flips, updates the database, and shows a callback alert confirmation. Click `Save & Close` to save.

### 2. LeetCode Problems, AI, and Streaks
* **Action**: Send `/daily`, `/random easy two-pointers`, and `/contest`.
  * **Expected**: Correct problem/contest cards are fetched and rendered with interactive links.
* **Action**: Send `/streak` and `/dstreak`.
  * **Expected**: `/streak` parses LeetCode submissionCalendar calendar to return active days. `/dstreak` calculates consecutive days solved from local challenge logs.
* **Action**: Send `/hint two-sum`.
  * **Expected**: Renders Hint 1 (Conceptual) with a button `Get Hint 2`. Clicking details Hint 2 (Strategic), which adds a button `Get Hint 3`. Hint 3 (Detailed Pseudo-code) completes the flow.
* **Action**: Send `/analyze` (or reply to a code block with `/analyze`).
  * **Expected**: Time/space Big-O analysis from Groq Llama 3.3.
* **Action**: Send `/review` (or reply to a code block with `/review`).
  * **Expected**: Complete code auditing and code quality recommendations from Gemini Flash 2.0.
* **Action**: Send `/visualize <code>` (or reply to a code block with `/visualize`).
  * **Expected**: Bot generates a Mermaid flowchart via Groq (Llama 3.3), encodes and renders it via `mermaid.ink` as a photo, and replies with a detailed step-by-step trace explanation of variables.

### 3. Spaced Repetition System (SRS)
* **Action**: Send `/solved`.
  * **Expected**: List of the 5 most recent accepted LeetCode submissions fetched dynamically.
* **Action**: Click on a problem button.
  * **Expected**: Prompts with grading callback buttons (0 - Forgot to 5 - Perfect).
* **Action**: Click a grading option (e.g., `4 - Easy`).
  * **Expected**: Database records review, calculates next date using SuperMemo SM-2, logs parameters (interval, ease factor), and awards 15 XP & 5 coins.

### 4. Multiplayer Coding Battles (Group Chat)
* **Action**: In a group, send `/battle @opponent_username`.
  * **Expected**: Invitation card appears with `Accept` and `Decline` buttons.
* **Action**: Opponent clicks `Accept`.
  * **Expected**: Starts a 60-minute active battle, cancels other pending challenges for both players, and lists the problem link.
* **Action**: In a group, send `/battle open` (or `/battle open easy arrays`).
  * **Expected**: Open battle lobby card is created showing problem title, difficulty, and lists joined participants. Inside are inline buttons for `🎮 Join Battle` and `🏁 Start Battle`.
* **Action**: Other group members click `🎮 Join Battle`.
  * **Expected**: Bot updates the lobby message dynamically, listing the new participants.
* **Action**: Battle creator clicks `🏁 Start Battle`.
  * **Expected**: Entry pool is locked, the battle status changes to `ACTIVE` with a 60-minute deadline, and the problem link is sent to the group.
* **Action**: Propose a pause using `/pausebattle`.
  * **Expected**: Pause prompt shows up. Opponent clicks `Accept Pause`. Battle status becomes `PAUSED` and the timer freezes.
* **Action**: Propose to resume using `/resumebattle`.
  * **Expected**: Resume prompt appears. Opponent has 5 minutes to accept. If they fail to click `Accept Resume` within 5 minutes, they forfeit, and the proposer is declared the winner (awarded 100 XP & 20 coins).
* **Action**: Propose a draw using `/stopbattle`.
  * **Expected**: Draw prompt appears. Opponent clicks `Decline Draw`. Prompt changes to ask proposer to Forfeit or Keep Playing. Clicking `Forfeit` awards opponent the win.
* **Action**: Complete a battle by solving the problem on LeetCode.
  * **Expected**: The scheduler detects the solve, updates battle/participant status, notifies the group of the solve timing, and compiles a final ranking leaderboard once everyone has solved or the 60-minute limit is reached. Rewards are distributed tier-wise (1st: 150 XP/30 coins, 2nd: 100 XP/20 coins, 3rd: 75 XP/15 coins, others who solved: 50 XP/10 coins, unsolved: 10 XP/0 coins).

### 5. Group-Specific Administration
* **Action**: Send `/config_group battles disable` as a group admin.
  * **Expected**: Confirms setting disabled. Trying to run `/battle` yields an error message.
* **Action**: Send `/mute_battle @member_username on` as the group owner.
  * **Expected**: Member is blocked from initiating or accepting battles in the group.
* **Action**: Send `/clear_group_history` as the group owner.
  * **Expected**: Group leaderboard stats reset to zero.

### 6. Global Administration & Security
* **Action**: Send `/ping` and `/stats` as a coordinator/admin.
  * **Expected**: Latency metrics (API & Database) and global system usage statistics are returned.
* **Action**: Send `/userinfo @user_username` as coordinator.
  * **Expected**: Detailed inspection summary of roles, ban status, and stats.
* **Action**: Send `/pban @user_username "Spamming"` as coordinator.
  * **Expected**: User is globally banned, cached in Redis, sent a ban notification, and blocked from all bot commands.
* **Action**: Send `/maintenance on` as a super admin.
  * **Expected**: Global maintenance mode enabled. Regular users trying to interact with the bot receive a block notice.
* **Action**: Send `/broadcast <b>Update:</b> Bot is operating normally.` as super admin.
  * **Expected**: Broadcast runs asynchronously, delivering the HTML message directly to all registered users in private DMs.

---

## Verification Troubleshooting

* **IPv6 Supabase Connections**: If database queries hang or timeout locally, ensure you are running Cloudflare WARP or a similar VPN supporting IPv6 database endpoints.
* **Long Polling vs Webhooks**: For local testing, keep the `WEBHOOK_URL` commented out in `.env` to fall back to Long Polling. Ensure the production webhook is properly registered using `WEBHOOK_URL` and `WEBHOOK_PATH`.
