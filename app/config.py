from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://spoonbill:spoonbill_dev@localhost:5432/spoonbill"
    
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    
    underwriting_amount_threshold_cents: int = 100000
    underwriting_auto_approve_below_cents: int = 10000
    
    admin_email: str = "admin@spoonbill.com"
    admin_password: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
