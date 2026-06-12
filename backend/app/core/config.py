from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str = "fallback"
    DATABASE_URL: str
    REDIS_URL: str
    PLANNING_HORIZON_DAYS: int = 21
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars to be more robust
    )

settings = Settings()
