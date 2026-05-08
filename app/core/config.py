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

    # Public base URL (used in API responses)
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Frontend base URL (used in QR code verify link)
    FRONTEND_URL: str = "http://localhost:3000/certificate"

    # Google Auth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_ALLOWED_DOMAINS: str = "siu.edu.vn"

    # LDAP Auth
    LDAP_SERVER_HOST: str = "127.0.0.1"
    LDAP_SERVER_PORT: int = 389
    LDAP_USE_TLS: bool = False
    LDAP_VALIDATE_CERT: bool = False
    LDAP_APP_DN: str = ""
    LDAP_APP_PASSWORD: str = ""
    LDAP_SEARCH_BASE: str = ""
    LDAP_ATTRIBUTE_FOR_MAIL: str = "mail"
    LDAP_ATTRIBUTE_FOR_USERNAME: str = "uid"

    # Initial admin seed
    ADMIN_EMAIL: str = "admin@siu.edu.vn"
    ADMIN_PASSWORD: str = "Admin@123"
    ADMIN_FULL_NAME: str = "System Admin"
    ADMIN_AUTO_SEED: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
