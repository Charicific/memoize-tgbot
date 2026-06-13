import os
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
    GEMINI_API_KEY: str
    
    # Webhook & Server Settings
    PORT: int = 8000
    WEBHOOK_URL: str = ""  # If empty, polling mode is used for local testing
    WEBHOOK_PATH: str = "/webhook"
    
    # Battle check frequency (in seconds)
    BATTLE_POLL_INTERVAL: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings(_env_file=".env")
