import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_URL_DIRECT: str = os.getenv("DATABASE_URL_DIRECT", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/tmp/kirana-output")
    SERVICE_URL: str = os.getenv("SERVICE_URL", "")
    WEBHOOK_PATH: str = "webhook"
    HEALTH_PATH: str = "health"


settings = Settings()
