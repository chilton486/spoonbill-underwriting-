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
    
    # Practice Portal base URL for invite links (set-password flow)
    # Default: http://localhost:5174 (local dev)
    # Staging: https://spoonbill-staging-portal.onrender.com
    practice_portal_base_url: str = "http://localhost:5174"
    
    # Intake Portal base URL
    # Default: http://localhost:5175 (local dev)
    # Staging: https://spoonbill-staging-intake.onrender.com
    intake_portal_base_url: str = "http://localhost:5175"
    
    # Email (SendGrid)
    sendgrid_api_key: str = ""
    email_from_address: str = "noreply@spoonbill.com"
    email_internal_alerts: str = ""

    # LLM (OpenAI) for ontology briefs
    openai_api_key: str = ""

    # Auto-run alembic migrations on startup (set to "true" in staging)
    run_migrations_on_startup: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_cors_origins(self) -> list[str]:
        """Get list of CORS allowed origins, combining defaults with env var.

        - Strips whitespace
        - Removes trailing slashes
        - Deduplicates
        """
        default_origins = [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:3000",
        ]

        all_origins = list(default_origins)

        if self.cors_allowed_origins:
            for origin in self.cors_allowed_origins.split(","):
                cleaned = origin.strip().rstrip("/")
                if cleaned and cleaned not in all_origins:
                    all_origins.append(cleaned)

        return all_origins


@lru_cache()
def get_settings() -> Settings:
    return Settings()
