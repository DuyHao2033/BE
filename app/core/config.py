from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SIU Digital Certificate"
    APP_ENV: str = "development"

    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    LOG_LEVEL: str = "info"

    # File storage
    UPLOAD_DIR: str = "./uploads"

    # Public base URL (used in QR code verify link)
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"


settings = Settings()
