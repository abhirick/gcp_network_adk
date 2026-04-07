from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    adk_model: str = os.getenv("ADK_MODEL", "gemini-2.5-pro")
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "abhishek")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west2")
    default_insight_location: str = os.getenv("DEFAULT_INSIGHT_LOCATION", "europe-west2")
    default_max_insights_per_type: int = int(
        os.getenv("DEFAULT_MAX_INSIGHTS_PER_TYPE", "100")
    )
    http_timeout_seconds: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()