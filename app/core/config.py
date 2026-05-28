from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Ganti dengan domain shared hosting Anda
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "https://yourdomain.com",
        "https://www.yourdomain.com",
    ]
    API_PREFIX: str = "/api/v1"

settings = Settings()
