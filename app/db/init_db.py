"""Create tables, then seed. Called by entrypoint.sh on every container start.

Tables are created with SQLAlchemy's create_all rather than Alembic. For a
schema that ships complete this is enough; see README for adding Alembic when
you need to change the schema without losing data.
"""
import logging

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import *  # noqa: F401,F403  (registers every model on Base)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("abeokuta.init")


def main() -> None:
    sqlite_path = settings.sqlite_path
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("SQLite file: %s", sqlite_path)

    Base.metadata.create_all(bind=engine)
    logger.info("Schema ready (%d tables)", len(Base.metadata.tables))

    if settings.SEED_ON_STARTUP:
        from app.db.seed import run

        run()
    else:
        logger.info("SEED_ON_STARTUP is false; skipping seed")


if __name__ == "__main__":
    main()
