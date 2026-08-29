import os
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import get_settings

logger = logging.getLogger("alunamda.database")

settings = get_settings()

# Use DATA_DIR env var if set (for Docker deployments), otherwise use config
data_dir = os.environ.get("DATA_DIR", settings.data_dir)
if data_dir != "./data":
    # Docker deployment: use DATA_DIR for all data
    database_url = os.environ.get(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{data_dir}/db/alunamda.db"
    )
else:
    database_url = settings.database_url

db_path = Path(database_url.replace("sqlite+aiosqlite:///", ""))
db_dir = db_path.parent
db_dir.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"timeout": 30},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def _set_sqlite_pragma(conn):
    for pragma in [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA foreign_keys=ON",
        "PRAGMA busy_timeout=5000",
        "PRAGMA cache_size=-64000",
    ]:
        await conn.execute(text(pragma))
    logger.info("SQLite PRAGMAs set: WAL mode, synchronous=NORMAL, foreign_keys=ON, busy_timeout=5000, cache_size=64MB")


async def init_db():
    async with engine.begin() as conn:
        await _set_sqlite_pragma(conn)
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_default_settings()
    await _check_integrity()
    _run_backup()


async def _ensure_default_settings():
    from models import CompanySettings
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id FROM company_settings LIMIT 1")
        )
        if not result.fetchone():
            settings_row = CompanySettings(id="settings_main")
            session.add(settings_row)
            await session.commit()
            logger.info("Created default company settings")


async def _check_integrity():
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA integrity_check"))
        status = result.scalar()
        if status != "ok":
            logger.error("Database integrity check failed: %s", status)
            raise RuntimeError(f"Database integrity check failed: {status}")
        logger.info("Database integrity check passed")


BACKUP_DIR = db_dir / "backups"
MAX_BACKUPS = 7


def _run_backup():
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"alunamda_{timestamp}.db"

        if db_path.exists():
            shutil.copy2(db_path, backup_file)
            logger.info("Database backup created: %s", backup_file.name)

            backups = sorted(BACKUP_DIR.glob("alunamda_*.db"), key=os.path.getmtime)
            while len(backups) > MAX_BACKUPS:
                oldest = backups.pop(0)
                oldest.unlink()
                logger.info("Removed old backup: %s", oldest.name)
    except Exception as e:
        logger.warning("Backup failed (non-fatal): %s", e)


async def dispose_engine():
    await engine.dispose()
    logger.info("Database engine disposed")
