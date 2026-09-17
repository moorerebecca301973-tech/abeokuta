"""Create tables, then seed. Called by entrypoint.sh on every container start.

Tables are created with SQLAlchemy's create_all rather than Alembic. For a
schema that ships complete this is enough; see README for adding Alembic when
you need to change the schema without losing data.
"""
import logging

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
# Import the modules, not names: this registers every table on Base.metadata
# and still works if app/models/__init__.py is ever missing.
from app.models import attraction, booking, misc, user  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("abeokuta.init")


def main() -> None:
    sqlite_path = settings.sqlite_path
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("SQLite file: %s", sqlite_path)

    table_count = len(Base.metadata.tables)
    if table_count == 0:
        raise RuntimeError(
            "No tables registered on Base.metadata. This almost always means a "
            "package __init__.py is missing from the image, so app.models "
            "resolved as an empty namespace package."
        )

    Base.metadata.create_all(bind=engine)
    logger.info("Schema ready (%d tables)", table_count)

    if not settings.database_url.startswith("sqlite:////") and settings.is_production:
        logger.warning(
            "DATABASE_URL is a relative path (%s). On Render this writes to the "
            "container filesystem and is destroyed on every deploy. Use four "
            "slashes: sqlite:////data/abeokuta.db",
            settings.database_url,
        )

    if settings.SEED_ON_STARTUP:
        from app.db.seed import run

        run()
    else:
        logger.info("SEED_ON_STARTUP is false; skipping seed")


if __name__ == "__main__":
    main()
