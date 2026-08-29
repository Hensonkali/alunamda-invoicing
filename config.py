import os
import logging
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ALUNAMDA Invoicing"
    app_version: str = "2.1.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./db/alunamda.db"
    secret_key: str = "alunamda-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    items_per_page: int = 25
    activity_per_page: int = 50
    max_upload_size_mb: int = 10
    allowed_upload_extensions: str = ".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.gif"
    default_country: str = "South Africa"
    settings_id: str = "settings_main"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    base_url: str = "http://localhost:3000"
    data_dir: str = "./data"


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return logging.getLogger("alunamda")


@lru_cache
def get_settings() -> Settings:
    return Settings()


logger = setup_logging(get_settings().debug)
