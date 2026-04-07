from __future__ import annotations

import logging
import sys
from logging.config import dictConfig

from gcp_network_adk.config import settings


def configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s | %(levelname)s | %(name)s | "
                        "%(funcName)s | %(message)s"
                    )
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "standard",
                    "level": settings.log_level,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": settings.log_level,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)