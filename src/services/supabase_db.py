import logging
import datetime
from typing import Optional, List, Dict, Any
import asyncpg
from src.config import settings
import json
from cachetools import TTLCache
from src.services.redis_cache import cache_manager

logger = logging.getLogger(__name__)

class SupabaseDB:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        # Store up to 1024 objects locally in RAM with short 60s expirations
        self.l1_settings_cache = TTLCache(maxsize=1024, ttl=60)
        self.l1_profile_cache = TTLCache(maxsize=1024, ttl=60)
        self.l1_mute_cache = TTLCache(maxsize=1024, ttl=60)
        self.l1_link_cache = TTLCache(maxsize=1024, ttl=300)


    async def connect(self):
        if not self.pool:
            try:
                # Direct PostgreSQL connection pool (asyncpg requires postgresql:// scheme)
                dsn = settings.SUPABASE_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
                self.pool = await asyncpg.create_pool(dsn, ssl='require')
                logger.info("Database connection pool established.")

                # Check/create group_members table if not exists
                await self.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    group_id BIGINT,
                    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    PRIMARY KEY (group_id, telegram_id)
                );
                """)
                logger.info("Checked/Created group_members table.")

                # Add reminder settings and role columns if they don't exist
                await self.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS remind_daily BOOLEAN DEFAULT TRUE;")
                await self.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS remind_streak BOOLEAN DEFAULT TRUE;")
                await self.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS remind_contests BOOLEAN DEFAULT TRUE;")
                await self.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'USER';")
                await self.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;")
                logger.info("Checked/Added reminder settings, role and is_banned columns to users table.")

                await self.execute("""
                CREATE TABLE IF NOT EXISTS daily_challenges (
                    date DATE PRIMARY KEY,
                    problem_slug VARCHAR(255) NOT NULL
                );
                """)
                logger.info("Checked/Created daily_challenges table.")

                # Check/create group_settings table
                await self.execute("""
                CREATE TABLE IF NOT EXISTS group_settings (
                    group_id BIGINT,
                    setting_name VARCHAR(100),
                    setting_value VARCHAR(255),
                    PRIMARY KEY (group_id, setting_name)
                );
                """)
                logger.info("Checked/Created group_settings table.")

                # Check/create group_battle_mutes table
                await self.execute("""
                CREATE TABLE IF NOT EXISTS group_battle_mutes (
                    group_id BIGINT,
                    telegram_id BIGINT,
                    muted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, telegram_id)
                );
                """)
                logger.info("Checked/Created group_battle_mutes table.")

                # Check/create group_battles table
                await self.execute("""
                CREATE TABLE IF NOT EXISTS group_battles (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    group_id BIGINT NOT NULL,
                    problem_slug VARCHAR(255) NOT NULL,
                    problem_title VARCHAR(255) NOT NULL,
                    difficulty VARCHAR(50) NOT NULL,
                    status VARCHAR(50) DEFAULT 'PENDING',
                    created_by BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    starts_at TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    message_id BIGINT
                );
                """)
                logger.info("Checked/Created group_battles table.")

                # Check/create group_battle_participants table
                await self.execute("""
                CREATE TABLE IF NOT EXISTS group_battle_participants (
                    group_battle_id UUID REFERENCES group_battles(id) ON DELETE CASCADE,
                    telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    solved_at TIMESTAMP WITH TIME ZONE,
                    solve_time_seconds INT,
                    PRIMARY KEY (group_battle_id, telegram_id)
                );
                """)
                logger.info("Checked/Created group_battle_participants table.")

                # Check/create bot_channels table
                await self.execute("""
                CREATE TABLE IF NOT EXISTS bot_channels (
                    channel_id BIGINT PRIMARY KEY,
                    title TEXT,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                logger.info("Checked/Created bot_channels table.")

                # Create performance indexes
                await self.execute("CREATE INDEX IF NOT EXISTS idx_problem_history_solved_at ON problem_history(solved_at);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_problem_history_slug ON problem_history(problem_slug);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_problem_history_user_solved ON problem_history(telegram_id, solved_at DESC);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_srs_reviews_next_date ON srs_reviews(next_review_date);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_battles_status ON battles(status);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_group_members_id ON group_members(telegram_id);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_group_battles_status ON group_battles(status);")
                await self.execute("CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users (LOWER(username));")
                logger.info("Initialized performance database indexes.")

                # Add paused_at and remaining_seconds columns to battles table
                await self.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP WITH TIME ZONE;")
                await self.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS remaining_seconds INT;")
                await self.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS chat_id BIGINT;")
                await self.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS message_id BIGINT;")
                await self.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS difficulty VARCHAR(50);")
                logger.info("Checked/Added paused_at, remaining_seconds, chat_id, message_id, and difficulty columns to battles table.")

                # Add paused_at and remaining_seconds columns to group_battles table
                await self.execute("ALTER TABLE group_battles ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP WITH TIME ZONE;")
                await self.execute("ALTER TABLE group_battles ADD COLUMN IF NOT EXISTS remaining_seconds INT;")
                logger.info("Checked/Added paused_at and remaining_seconds columns to group_battles table.")

                # Clean up existing Telegram service account entries if present
                await self.execute("UPDATE battles SET winner_id = NULL WHERE winner_id = 777000;")
                await self.execute("DELETE FROM group_members WHERE telegram_id = 777000;")
                await self.execute("DELETE FROM users WHERE telegram_id = 777000;")
                logger.info("Checked/Cleaned up Telegram service account (777000) entries.")

            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise e


    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed.")

    async def execute(self, query: str, *args) -> str:
        import time
        start = time.time()
        async with self.pool.acquire() as conn:
            res = await conn.execute(query, *args)
        latency = (time.time() - start) * 1000
        if latency > 5000:
            logger.warning(f"SLOW DB Execute ({latency:.1f}ms): {query[:200]}")
        return res

    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        import time
        start = time.time()
        async with self.pool.acquire() as conn:
            res = await conn.fetch(query, *args)
        latency = (time.time() - start) * 1000
        if latency > 5000:
            logger.warning(f"SLOW DB Fetch ({latency:.1f}ms): {query[:200]}")
        return res

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        import time
        start = time.time()
        async with self.pool.acquire() as conn:
            res = await conn.fetchrow(query, *args)
        latency = (time.time() - start) * 1000
        if latency > 5000:
            logger.warning(f"SLOW DB Fetchrow ({latency:.1f}ms): {query[:200]}")
        return res

    # --- Users ---
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        cache_key = f"cache:user:profile:{telegram_id}"
        
        # 1. L1 RAM Cache Hit
        if cache_key in self.l1_profile_cache:
            return self.l1_profile_cache[cache_key]

        # 2. L2 Redis Cache Hit
        try:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                if cached_data == "__none__":
                    self.l1_profile_cache[cache_key] = None
                    return None
                user_dict = json.loads(cached_data)
                self.l1_profile_cache[cache_key] = user_dict
                return user_dict
        except Exception as e:
            logger.error(f"Redis L2 cache read error in get_user: {e}")

        # 3. Cache Miss -> Query PostgreSQL DB
        row = await self.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        user_dict = dict(row) if row else None

        # 4. Save to both L1 RAM and L2 Redis
        self.l1_profile_cache[cache_key] = user_dict
        try:
            if user_dict:
                await cache_manager.set(cache_key, json.dumps(user_dict, default=str), ex=3600)  # L2 TTL: 1 hour
            else:
                await cache_manager.set(cache_key, "__none__", ex=300)  # Negative cache L2 TTL: 5 minutes
        except Exception as e:
            logger.error(f"Redis L2 cache write error in get_user: {e}")

        return user_dict

    async def create_user(self, telegram_id: int, username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
        # Safety net: never record Telegram's service account
        if telegram_id == 777000:
            return {}
        query = """
        INSERT INTO users (telegram_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_id) DO UPDATE
        SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, username, first_name)
        user_dict = dict(row) if row else {}
        
        # Invalidate cache
        if user_dict:
            cache_key = f"cache:user:profile:{telegram_id}"
            self.l1_profile_cache.pop(cache_key, None)
            try:
                await cache_manager.delete(cache_key)
            except Exception as e:
                logger.error(f"Failed to invalidate user cache key {cache_key} in create_user: {e}")
                
        return user_dict

    async def add_xp_coins(self, telegram_id: int, xp: int, coins: int) -> Optional[Dict[str, Any]]:
        query = """
        UPDATE users
        SET xp = xp + $2, coins = coins + $3,
            level = 1 + FLOOR((xp + $2) / 100)::int
        WHERE telegram_id = $1
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, xp, coins)
        if row:
            cache_key = f"cache:user:profile:{telegram_id}"
            # Invalidate L1 cache
            self.l1_profile_cache.pop(cache_key, None)
            try:
                # Invalidate user profile L2 cache
                await cache_manager.delete(cache_key)
                
                # Invalidate global leaderboard cache
                await cache_manager.delete("global_leaderboard")
                
                # Invalidate group leaderboard cache for all groups user belongs to
                groups = await self.fetch("SELECT group_id FROM group_members WHERE telegram_id = $1", telegram_id)
                for g in groups:
                    await cache_manager.delete(f"group_leaderboard:{g['group_id']}")
            except Exception as e:
                logger.error(f"Error invalidating cache in add_xp_coins: {e}")
        return dict(row) if row else None

    # --- Linked Accounts ---
    async def get_linked_account(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        cache_key = f"cache:linked_account:{telegram_id}"
        
        # 1. L1 RAM Cache Hit
        if cache_key in self.l1_link_cache:
            return self.l1_link_cache[cache_key]

        # 2. L2 Redis Cache Hit
        try:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                if cached_data == "__none__":
                    self.l1_link_cache[cache_key] = None
                    return None
                link_dict = json.loads(cached_data)
                self.l1_link_cache[cache_key] = link_dict
                return link_dict
        except Exception as e:
            logger.error(f"Redis L2 cache read error in get_linked_account: {e}")

        # 3. Cache Miss -> Query PostgreSQL DB
        row = await self.fetchrow("SELECT * FROM linked_accounts WHERE telegram_id = $1", telegram_id)
        link_dict = dict(row) if row else None

        # 4. Save to both L1 RAM and L2 Redis
        self.l1_link_cache[cache_key] = link_dict
        try:
            if link_dict:
                await cache_manager.set(cache_key, json.dumps(link_dict, default=str), ex=3600)  # L2 TTL: 1 hour
            else:
                await cache_manager.set(cache_key, "__none__", ex=300)  # Negative cache L2 TTL: 5 minutes
        except Exception as e:
            logger.error(f"Redis L2 cache write error in get_linked_account: {e}")

        return link_dict

    async def get_verified_links_for_users(self, telegram_ids: List[int]) -> Dict[int, str]:
        if not telegram_ids:
            return {}
        rows = await self.fetch(
            "SELECT telegram_id, leetcode_username FROM linked_accounts WHERE telegram_id = ANY($1::bigint[]) AND verified = TRUE",
            telegram_ids
        )
        return {r["telegram_id"]: r["leetcode_username"] for r in rows}

    async def get_user_by_leetcode(self, leetcode_username: str) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM linked_accounts WHERE leetcode_username = $1 AND verified = TRUE", leetcode_username)
        return dict(row) if row else None

    async def link_leetcode_account(self, telegram_id: int, leetcode_username: str, verification_code: str) -> Dict[str, Any]:
        query = """
        INSERT INTO linked_accounts (telegram_id, leetcode_username, verification_code, verified)
        VALUES ($1, $2, $3, FALSE)
        ON CONFLICT (telegram_id) DO UPDATE
        SET leetcode_username = EXCLUDED.leetcode_username,
            verification_code = EXCLUDED.verification_code,
            verified = FALSE
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, leetcode_username, verification_code)
        link_dict = dict(row) if row else {}
        
        # Invalidate cache
        if link_dict:
            cache_key = f"cache:linked_account:{telegram_id}"
            self.l1_link_cache.pop(cache_key, None)
            try:
                await cache_manager.delete(cache_key)
            except Exception as e:
                logger.error(f"Failed to invalidate linked account cache key {cache_key} in link_leetcode_account: {e}")
                
        return link_dict

    async def verify_leetcode_account(self, telegram_id: int) -> bool:
        query = """
        UPDATE linked_accounts
        SET verified = TRUE
        WHERE telegram_id = $1
        RETURNING verified
        """
        row = await self.fetchrow(query, telegram_id)
        verified = row["verified"] if row else False
        
        # Invalidate cache
        cache_key = f"cache:linked_account:{telegram_id}"
        self.l1_link_cache.pop(cache_key, None)
        try:
            await cache_manager.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to invalidate linked account cache key {cache_key} in verify_leetcode_account: {e}")
            
        return verified

    # --- Problem History ---
    async def record_solved_problem(self, telegram_id: int, problem_slug: str, problem_title: str, difficulty: str) -> bool:
        query = """
        INSERT INTO problem_history (telegram_id, problem_slug, problem_title, difficulty)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (telegram_id, problem_slug) DO NOTHING
        RETURNING id
        """
        row = await self.fetchrow(query, telegram_id, problem_slug, problem_title, difficulty)
        return row is not None

    async def get_problem_history(self, telegram_id: int) -> List[Dict[str, Any]]:
        rows = await self.fetch("SELECT * FROM problem_history WHERE telegram_id = $1 ORDER BY solved_at DESC", telegram_id)
        return [dict(r) for r in rows]

    # --- SRS Reviews ---
    async def get_srs_review(self, telegram_id: int, problem_slug: str) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM srs_reviews WHERE telegram_id = $1 AND problem_slug = $2", telegram_id, problem_slug)
        return dict(row) if row else None

    async def save_srs_review(self, telegram_id: int, problem_slug: str, ease_factor: float, interval: int, repetitions: int, next_review_date: datetime.datetime, quality: int) -> Dict[str, Any]:
        query = """
        INSERT INTO srs_reviews (telegram_id, problem_slug, ease_factor, interval, repetitions, next_review_date, last_quality)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (telegram_id, problem_slug) DO UPDATE
        SET ease_factor = EXCLUDED.ease_factor,
            interval = EXCLUDED.interval,
            repetitions = EXCLUDED.repetitions,
            next_review_date = EXCLUDED.next_review_date,
            last_quality = EXCLUDED.last_quality,
            updated_at = CURRENT_TIMESTAMP
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, problem_slug, ease_factor, interval, repetitions, next_review_date, quality)
        return dict(row)

    async def get_due_srs_reviews(self, telegram_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT r.*, h.problem_title, h.difficulty
        FROM srs_reviews r
        LEFT JOIN problem_history h ON r.telegram_id = h.telegram_id AND r.problem_slug = h.problem_slug
        WHERE r.telegram_id = $1 AND r.next_review_date::date <= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date
        ORDER BY r.next_review_date ASC
        """
        rows = await self.fetch(query, telegram_id)
        return [dict(r) for r in rows]

    async def get_user_srs_reviews(self, telegram_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT r.*, h.problem_title, h.difficulty
        FROM srs_reviews r
        LEFT JOIN problem_history h ON r.telegram_id = h.telegram_id AND r.problem_slug = h.problem_slug
        WHERE r.telegram_id = $1
        ORDER BY r.next_review_date ASC
        """
        rows = await self.fetch(query, telegram_id)
        return [dict(r) for r in rows]

    async def delete_srs_review(self, telegram_id: int, problem_slug: str) -> bool:
        query = """
        DELETE FROM srs_reviews
        WHERE telegram_id = $1 AND problem_slug = $2
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, problem_slug)
        return row is not None

    # --- Battles ---
    async def create_battle(self, challenger_id: int, opponent_id: int, problem_slug: str, problem_title: str, difficulty: str, expires_at: datetime.datetime) -> Dict[str, Any]:
        query = """
        INSERT INTO battles (challenger_id, opponent_id, problem_slug, problem_title, difficulty, status, expires_at)
        VALUES ($1, $2, $3, $4, $5, 'PENDING', $6)
        RETURNING *
        """
        row = await self.fetchrow(query, challenger_id, opponent_id, problem_slug, problem_title, difficulty, expires_at)
        return dict(row)

    async def update_battle_message(self, battle_id: str, chat_id: int, message_id: int):
        await self.execute(
            "UPDATE battles SET chat_id = $2, message_id = $3 WHERE id = $1::uuid",
            battle_id, chat_id, message_id
        )

    async def get_battle(self, battle_id: str) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM battles WHERE id = $1::uuid", battle_id)
        return dict(row) if row else None

    async def get_active_battles(self) -> List[Dict[str, Any]]:
        rows = await self.fetch("SELECT * FROM battles WHERE status = 'ACTIVE' OR status = 'PENDING'")
        return [dict(r) for r in rows]

    async def update_battle_status(self, battle_id: str, status: str, winner_id: Optional[int] = None, started_at: Optional[datetime.datetime] = None, ended_at: Optional[datetime.datetime] = None) -> Optional[Dict[str, Any]]:
        query = """
        UPDATE battles
        SET status = $2,
            winner_id = COALESCE($3, winner_id),
            started_at = COALESCE($4, started_at),
            ended_at = COALESCE($5, ended_at)
        WHERE id = $1::uuid
        RETURNING *
        """
        row = await self.fetchrow(query, battle_id, status, winner_id, started_at, ended_at)
        return dict(row) if row else None

    # --- Leaderboards ---
    async def get_global_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        SELECT telegram_id, username, first_name, xp, level, coins
        FROM users
        ORDER BY xp DESC
        LIMIT $1
        """
        rows = await self.fetch(query, limit)
        return [dict(r) for r in rows]

    # --- System Stats ---
    async def get_bot_stats(self) -> Dict[str, int]:
        query = """
        SELECT
            (SELECT COUNT(*) FROM users) AS total_users,
            (SELECT COUNT(*) FROM linked_accounts) AS total_linked,
            (SELECT COUNT(*) FROM linked_accounts WHERE verified = TRUE) AS total_verified,
            (SELECT COUNT(*) FROM battles) AS total_battles,
            (SELECT COUNT(*) FROM battles WHERE status IN ('ACTIVE', 'PENDING')) AS active_battles,
            (SELECT COUNT(*) FROM battles WHERE status = 'COMPLETED') AS completed_battles,
            (SELECT COUNT(*) FROM problem_history) AS total_solved,
            (SELECT COUNT(*) FROM srs_reviews) AS total_srs,
            (SELECT COUNT(DISTINCT group_id) FROM group_members) AS total_groups,
            (SELECT COUNT(*) FROM bot_channels) AS total_channels,
            (
                SELECT COUNT(*) FROM users
                WHERE COALESCE(remind_daily, TRUE) = TRUE
                   OR COALESCE(remind_streak, TRUE) = TRUE
                   OR COALESCE(remind_contests, TRUE) = TRUE
            ) AS reminder_users
        """
        row = await self.fetchrow(query)
        if row:
            return dict(row)
        return {
            "total_users": 0,
            "total_linked": 0,
            "total_verified": 0,
            "total_battles": 0,
            "active_battles": 0,
            "completed_battles": 0,
            "total_solved": 0,
            "total_srs": 0,
            "total_groups": 0,
            "total_channels": 0,
            "reminder_users": 0,
        }

    # --- Group Memberships & Leaderboards ---
    async def record_group_member(self, group_id: int, telegram_id: int, username: Optional[str], first_name: Optional[str]):
        # Ensure user exists in users table first
        await self.create_user(telegram_id, username, first_name)
        # Record group membership
        query = """
        INSERT INTO group_members (group_id, telegram_id)
        VALUES ($1, $2)
        ON CONFLICT (group_id, telegram_id) DO NOTHING
        """
        await self.execute(query, group_id, telegram_id)

    async def get_group_leaderboard(self, group_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
        SELECT u.telegram_id, u.username, u.first_name, u.xp, u.level, u.coins
        FROM users u
        JOIN group_members gm ON u.telegram_id = gm.telegram_id
        WHERE gm.group_id = $1
        ORDER BY u.xp DESC
        LIMIT $2
        """
        rows = await self.fetch(query, group_id, limit)
        return [dict(r) for r in rows]


    async def update_reminder_setting(self, telegram_id: int, setting_name: str, value: bool) -> Optional[Dict[str, Any]]:
        if setting_name not in ["remind_daily", "remind_streak", "remind_contests"]:
            raise ValueError(f"Invalid setting name: {setting_name}")
        
        query = f"""
        UPDATE users
        SET {setting_name} = $2
        WHERE telegram_id = $1
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, value)
        
        # Invalidate cache
        cache_key = f"cache:user:profile:{telegram_id}"
        self.l1_profile_cache.pop(cache_key, None)
        try:
            await cache_manager.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to invalidate L2 user cache key {cache_key} in update_reminder_setting: {e}")
            
        return dict(row) if row else None

    async def get_users_with_daily_reminders(self) -> List[int]:
        query = "SELECT telegram_id FROM users WHERE COALESCE(remind_daily, TRUE) = TRUE"
        rows = await self.fetch(query)
        return [r["telegram_id"] for r in rows]

    async def get_users_with_contest_reminders(self) -> List[int]:
        query = "SELECT telegram_id FROM users WHERE COALESCE(remind_contests, TRUE) = TRUE"
        rows = await self.fetch(query)
        return [r["telegram_id"] for r in rows]

    async def get_users_for_streak_check(self) -> List[Dict[str, Any]]:
        query = """
        SELECT u.telegram_id, la.leetcode_username
        FROM users u
        LEFT JOIN linked_accounts la ON u.telegram_id = la.telegram_id AND la.verified = TRUE
        WHERE COALESCE(u.remind_streak, TRUE) = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM problem_history ph
              WHERE ph.telegram_id = u.telegram_id
                AND ph.solved_at >= CURRENT_DATE AND ph.solved_at < CURRENT_DATE + INTERVAL '1 day'
          )
        """
        rows = await self.fetch(query)
        return [dict(r) for r in rows]

    async def record_daily_challenge(self, date_str: str, problem_slug: str):
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        query = """
        INSERT INTO daily_challenges (date, problem_slug)
        VALUES ($1, $2)
        ON CONFLICT (date) DO UPDATE SET problem_slug = EXCLUDED.problem_slug
        """
        await self.execute(query, date_obj, problem_slug)

    async def get_user_daily_challenge_dates(self, telegram_id: int) -> List[datetime.date]:
        query = """
        SELECT DISTINCT dc.date AS solve_date
        FROM daily_challenges dc
        JOIN problem_history ph ON dc.problem_slug = ph.problem_slug
        WHERE ph.telegram_id = $1
          AND ph.solved_at >= dc.date
          AND ph.solved_at < dc.date + INTERVAL '1 day'
        ORDER BY solve_date DESC
        """
        rows = await self.fetch(query, telegram_id)
        return [r["solve_date"] for r in rows]

    # --- Group Settings & Battle Mutes ---
    async def get_group_setting(self, group_id: int, setting_name: str) -> Optional[str]:
        cache_key = f"cache:group:settings:{group_id}:{setting_name}"
        
        # 1. L1 RAM Cache Hit (Fastest)
        if cache_key in self.l1_settings_cache:
            return self.l1_settings_cache[cache_key]

        # 2. L2 Redis Cache Hit
        try:
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                if cached_value == "__none__":
                    self.l1_settings_cache[cache_key] = None
                    return None
                # Store in L1 RAM cache before returning
                self.l1_settings_cache[cache_key] = cached_value
                return cached_value
        except Exception as e:
            logger.error(f"Redis L2 cache read error in get_group_setting: {e}")

        # 3. L1/L2 Cache Miss -> Query PostgreSQL DB
        row = await self.fetchrow(
            "SELECT setting_value FROM group_settings WHERE group_id = $1 AND setting_name = $2",
            group_id, setting_name
        )
        val = row["setting_value"] if row else None

        # 4. Save to both L1 RAM and L2 Redis
        self.l1_settings_cache[cache_key] = val
        try:
            if val is not None:
                await cache_manager.set(cache_key, val, ex=600)  # L2 TTL: 10 mins
            else:
                await cache_manager.set(cache_key, "__none__", ex=300)  # Negative cache L2 TTL: 5 minutes
        except Exception as e:
            logger.error(f"Redis L2 cache write error in get_group_setting: {e}")
                
        return val

    async def set_group_setting(self, group_id: int, setting_name: str, setting_value: str):
        query = """
        INSERT INTO group_settings (group_id, setting_name, setting_value)
        VALUES ($1, $2, $3)
        ON CONFLICT (group_id, setting_name)
        DO UPDATE SET setting_value = EXCLUDED.setting_value
        """
        await self.execute(query, group_id, setting_name, setting_value)
        
        cache_key = f"cache:group:settings:{group_id}:{setting_name}"
        
        # Invalidate L1 Cache (RAM)
        self.l1_settings_cache.pop(cache_key, None)
        
        # Invalidate L2 Cache (Redis)
        try:
            await cache_manager.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to invalidate L2 cache key {cache_key}: {e}")

    async def mute_group_battle(self, group_id: int, telegram_id: int, mute: bool):
        if mute:
            await self.execute(
                "INSERT INTO group_battle_mutes (group_id, telegram_id) VALUES ($1, $2) ON CONFLICT (group_id, telegram_id) DO NOTHING",
                group_id, telegram_id
            )
        else:
            await self.execute(
                "DELETE FROM group_battle_mutes WHERE group_id = $1 AND telegram_id = $2",
                group_id, telegram_id
            )
            
        cache_key = f"cache:group:mute:{group_id}:{telegram_id}"
        
        # Invalidate L1 RAM
        self.l1_mute_cache.pop(cache_key, None)
        
        # Invalidate L2 Redis
        try:
            await cache_manager.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to invalidate L2 cache key {cache_key} in mute_group_battle: {e}")

    async def is_group_battle_muted(self, group_id: int, telegram_id: int) -> bool:
        cache_key = f"cache:group:mute:{group_id}:{telegram_id}"
        
        # 1. L1 RAM Cache Hit
        if cache_key in self.l1_mute_cache:
            return self.l1_mute_cache[cache_key] == '1'

        # 2. L2 Redis Cache Hit
        try:
            cached_val = await cache_manager.get(cache_key)
            if cached_val is not None:
                self.l1_mute_cache[cache_key] = cached_val
                return cached_val == '1'
        except Exception as e:
            logger.error(f"Redis L2 cache read error in is_group_battle_muted: {e}")

        # 3. Cache Miss -> Query PostgreSQL DB
        row = await self.fetchrow(
            "SELECT 1 FROM group_battle_mutes WHERE group_id = $1 AND telegram_id = $2",
            group_id, telegram_id
        )
        muted = row is not None
        val_str = '1' if muted else '0'

        # 4. Save to both L1 RAM and L2 Redis
        self.l1_mute_cache[cache_key] = val_str
        try:
            await cache_manager.set(cache_key, val_str, ex=600)  # L2 TTL: 10 mins
        except Exception as e:
            logger.error(f"Redis L2 cache write error in is_group_battle_muted: {e}")
            
        return muted

    async def clear_group_history(self, group_id: int):
        await self.execute("DELETE FROM group_members WHERE group_id = $1", group_id)

    async def get_user_by_id_or_username(self, identifier: str) -> Optional[Dict[str, Any]]:
        # Strip leading '@' if present
        cleaned = identifier.strip().lstrip('@')
        if cleaned.isdigit() or (cleaned.startswith('-') and cleaned[1:].isdigit()):
            # Treat as numeric Telegram ID
            row = await self.fetchrow("SELECT * FROM users WHERE telegram_id = $1", int(cleaned))
        else:
            # Treat as Telegram Username
            row = await self.fetchrow("SELECT * FROM users WHERE LOWER(username) = LOWER($1)", cleaned)
        return dict(row) if row else None

    # --- Group Battles ---
    async def create_group_battle(self, group_id: int, problem_slug: str, problem_title: str, difficulty: str, created_by: int, expires_at: datetime.datetime) -> Dict[str, Any]:
        query = """
        INSERT INTO group_battles (group_id, problem_slug, problem_title, difficulty, status, created_by, expires_at)
        VALUES ($1, $2, $3, $4, 'PENDING', $5, $6)
        RETURNING *
        """
        row = await self.fetchrow(query, group_id, problem_slug, problem_title, difficulty, created_by, expires_at)
        return dict(row)

    async def update_group_battle_message(self, battle_id: str, message_id: int):
        await self.execute(
            "UPDATE group_battles SET message_id = $2 WHERE id = $1::uuid",
            battle_id, message_id
        )

    async def get_group_battle(self, battle_id: str) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM group_battles WHERE id = $1::uuid", battle_id)
        return dict(row) if row else None

    async def get_active_group_battles(self) -> List[Dict[str, Any]]:
        rows = await self.fetch("SELECT * FROM group_battles WHERE status IN ('PENDING', 'ACTIVE')")
        return [dict(r) for r in rows]

    async def update_group_battle_status(self, battle_id: str, status: str, starts_at: Optional[datetime.datetime] = None, expires_at: Optional[datetime.datetime] = None) -> Optional[Dict[str, Any]]:
        query = """
        UPDATE group_battles
        SET status = $2,
            starts_at = COALESCE($3, starts_at),
            expires_at = COALESCE($4, expires_at)
        WHERE id = $1::uuid
        RETURNING *
        """
        row = await self.fetchrow(query, battle_id, status, starts_at, expires_at)
        return dict(row) if row else None

    async def join_group_battle(self, group_battle_id: str, telegram_id: int) -> bool:
        # Check if already joined
        row = await self.fetchrow(
            "SELECT 1 FROM group_battle_participants WHERE group_battle_id = $1::uuid AND telegram_id = $2",
            group_battle_id, telegram_id
        )
        if row:
            return False
        
        await self.execute(
            "INSERT INTO group_battle_participants (group_battle_id, telegram_id) VALUES ($1::uuid, $2)",
            group_battle_id, telegram_id
        )
        return True

    async def get_group_battle_participants(self, group_battle_id: str) -> List[Dict[str, Any]]:
        query = """
        SELECT gbp.*, u.username, u.first_name, u.xp, u.level
        FROM group_battle_participants gbp
        JOIN users u ON gbp.telegram_id = u.telegram_id
        WHERE gbp.group_battle_id = $1::uuid
        ORDER BY gbp.joined_at ASC
        """
        rows = await self.fetch(query, group_battle_id)
        return [dict(r) for r in rows]

    async def update_group_participant_solve(self, group_battle_id: str, telegram_id: int, solved_at: datetime.datetime, solve_time_seconds: int):
        query = """
        UPDATE group_battle_participants
        SET solved_at = $3,
            solve_time_seconds = $4
        WHERE group_battle_id = $1::uuid AND telegram_id = $2
        """
        await self.execute(query, group_battle_id, telegram_id, solved_at, solve_time_seconds)

    # --- Bot Channels ---

    async def record_bot_channel(self, channel_id: int, title: Optional[str]):
        """Record a channel the bot has been added to."""
        query = """
        INSERT INTO bot_channels (channel_id, title)
        VALUES ($1, $2)
        ON CONFLICT (channel_id) DO UPDATE SET title = EXCLUDED.title
        """
        await self.execute(query, channel_id, title)

    async def remove_bot_channel(self, channel_id: int):
        """Remove a channel the bot has been kicked from."""
        await self.execute("DELETE FROM bot_channels WHERE channel_id = $1", channel_id)

    async def get_all_channels(self) -> List[int]:
        """Return all channel IDs the bot is a member of."""
        rows = await self.fetch("SELECT channel_id FROM bot_channels")
        return [r["channel_id"] for r in rows]


# Global DB Instance
db = SupabaseDB()
