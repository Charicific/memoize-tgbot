import logging
import datetime
from typing import Optional, List, Dict, Any
import asyncpg
from src.config import settings

logger = logging.getLogger(__name__)

class SupabaseDB:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if not self.pool:
            try:
                # Direct PostgreSQL connection pool (asyncpg requires postgresql:// scheme)
                dsn = settings.SUPABASE_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
                self.pool = await asyncpg.create_pool(dsn)
                logger.info("Database connection pool established.")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise e

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed.")

    async def execute(self, query: str, *args) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    # --- Users ---
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
        query = """
        INSERT INTO users (telegram_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_id) DO UPDATE
        SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, username, first_name)
        return dict(row)

    async def add_xp_coins(self, telegram_id: int, xp: int, coins: int) -> Optional[Dict[str, Any]]:
        query = """
        UPDATE users
        SET xp = xp + $2, coins = coins + $3,
            level = 1 + FLOOR((xp + $2) / 100)::int
        WHERE telegram_id = $1
        RETURNING *
        """
        row = await self.fetchrow(query, telegram_id, xp, coins)
        return dict(row) if row else None

    # --- Linked Accounts ---
    async def get_linked_account(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchrow("SELECT * FROM linked_accounts WHERE telegram_id = $1", telegram_id)
        return dict(row) if row else None

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
        return dict(row)

    async def verify_leetcode_account(self, telegram_id: int) -> bool:
        query = """
        UPDATE linked_accounts
        SET verified = TRUE
        WHERE telegram_id = $1
        RETURNING verified
        """
        row = await self.fetchrow(query, telegram_id)
        return row["verified"] if row else False

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
        SELECT * FROM srs_reviews
        WHERE telegram_id = $1 AND next_review_date <= NOW()
        ORDER BY next_review_date ASC
        """
        rows = await self.fetch(query, telegram_id)
        return [dict(r) for r in rows]

    # --- Battles ---
    async def create_battle(self, challenger_id: int, opponent_id: int, problem_slug: str, problem_title: str, expires_at: datetime.datetime) -> Dict[str, Any]:
        query = """
        INSERT INTO battles (challenger_id, opponent_id, problem_slug, problem_title, status, expires_at)
        VALUES ($1, $2, $3, $4, 'PENDING', $5)
        RETURNING *
        """
        row = await self.fetchrow(query, challenger_id, opponent_id, problem_slug, problem_title, expires_at)
        return dict(row)

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

# Global DB Instance
db = SupabaseDB()
