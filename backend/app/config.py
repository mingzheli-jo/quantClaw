from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://quantclaw:quantclaw@localhost:5432/quantclaw"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    admin_username: str = "admin"
    admin_password: str = "admin123"

    feishu_webhook_url: str = ""

    base_url: str = "https://quant.azhefuye.online"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
