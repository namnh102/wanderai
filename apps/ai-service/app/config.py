from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/wanderai"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    PLANNER_MODEL: str = "gemini-3.5-flash"
    PLANNER_MAX_OUTPUT_TOKENS: int = 16384
    PLANNER_TIMEOUT_MS: int = 55000
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    WEATHER_API_URL: str = "https://api.open-meteo.com/v1"
    AI_PORT: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
