from pathlib import Path
from pydantic import BaseSettings
import logging
import logging.config

class Settings(BaseSettings):
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    knowledge_base_dir: Path = Path("knowledge_base")
    log_level: str = "INFO"

    class Config:
        env_prefix = "APP_"

    def setup_logging(self):
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": self.log_level
                }
            },
            "root": {
                "handlers": ["console"],
                "level": self.log_level
            }
        })

settings = Settings()