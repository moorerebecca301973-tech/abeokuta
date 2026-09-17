from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    # FastAPI runs sync endpoints in a threadpool, so a connection may be used
    # by a different thread than the one that created it.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    echo=settings.SQL_ECHO,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """SQLite's defaults are wrong for a web server. Fix them per connection."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")     # readers do not block the writer
    cursor.execute("PRAGMA synchronous=NORMAL")   # safe under WAL, much faster
    cursor.execute("PRAGMA foreign_keys=ON")      # OFF by default: FKs are decorative without this
    cursor.execute("PRAGMA busy_timeout=5000")    # wait for a lock instead of raising
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
