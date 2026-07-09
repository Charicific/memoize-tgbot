import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str

    # Supabase / Postgres
    SUPABASE_URL: str
    SUPABASE_KEY: str
    # Format: postgresql+asyncpg://user:pass@host:port/dbname or postgresql://
    SUPABASE_DB_URL: str

    # Upstash Redis
    REDIS_URL: str

    # AI API Keys
    GROQ_API_KEY: str
    NVIDIA_API_KEY: str
    OPENROUTER_API_KEY: Optional[str] = None

    # Webhook & Server Settings
    PORT: int = 8000
    WEBHOOK_URL: str = ""  # If empty, polling mode is used for local testing
    WEBHOOK_PATH: str = "/webhook"

    # Battle check frequency (in seconds)
    BATTLE_POLL_INTERVAL: int = 60

    # Log Channel Configuration
    LOG_CHANNEL_ID: Optional[int] = None
    PUBLIC_CHANNEL_ID: str = ""
    LEETCODE_FEED_CHANNEL_ID: str = ""
    SUPER_ADMIN_IDS: str = ""
    PROXIES: str = ""

    # UptimeRobot API Configuration
    UPTIMEROBOT_API_KEY: str = ""
    UPTIMEROBOT_MONITOR_ID: str = ""

    @property
    def proxies_list(self) -> list[str]:
        if not self.PROXIES:
            return []
        return [x.strip() for x in self.PROXIES.split(",") if x.strip()]

    @property
    def public_channels(self) -> list[int]:
        if not self.PUBLIC_CHANNEL_ID:
            return []
        ids = []
        for x in self.PUBLIC_CHANNEL_ID.split(","):
            val = x.strip()
            if val:
                try:
                    ids.append(int(val))
                except ValueError:
                    pass
        return ids

    @property
    def leetcode_feed_channels(self) -> list[int]:
        if not self.LEETCODE_FEED_CHANNEL_ID:
            return []
        ids = []
        for x in self.LEETCODE_FEED_CHANNEL_ID.split(","):
            val = x.strip()
            if val:
                try:
                    ids.append(int(val))
                except ValueError:
                    pass
        return ids

    @property
    def super_admin_ids(self) -> list[int]:
        if not self.SUPER_ADMIN_IDS:
            return []
        ids = []
        for x in self.SUPER_ADMIN_IDS.split(","):
            val = x.strip()
            if val:
                try:
                    ids.append(int(val))
                except ValueError:
                    pass
        return ids

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Instantiate settings
settings = Settings(_env_file=".env")
