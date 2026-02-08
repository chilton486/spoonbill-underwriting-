from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql://spoonbill:spoonbill_dev@localhost:5432/spoonbill"
    
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    
    underwriting_amount_threshold_cents: int = 100000
    underwriting_auto_approve_below_cents: int = 10000
    
    admin_email: str = "admin@spoonbill.com"
    admin_password: str = "changeme123"
    
    # CORS configuration - comma-separated list of allowed origins
    # Example: "https://console.example.com,https://portal.example.com"
    cors_allowed_origins: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_cors_origins(self) -> list[str]:
        """Get list of CORS allowed origins, combining defaults with env var."""
        # Default local development origins
        default_origins = [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:3000",
        ]
        
        if self.cors_allowed_origins:
            # Parse comma-separated origins from env var
            extra_origins = [
                origin.strip() 
                for origin in self.cors_allowed_origins.split(",") 
                if origin.strip()
            ]
            return default_origins + extra_origins
        
        return default_origins


@lru_cache()
def get_settings() -> Settings:
    return Settings()
