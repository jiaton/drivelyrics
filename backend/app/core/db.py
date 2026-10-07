from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(f"sqlite:///{settings.database_path}")


# pysqlite's own transaction handling skips DDL (a DROP TABLE commits on the spot), so
# a failed migration couldn't roll back. SQLAlchemy's documented fix: turn pysqlite's
# handling off and emit BEGIN ourselves.
@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")  # SSE pollers write while requests read
    cursor.execute("PRAGMA synchronous=NORMAL")  # safe under WAL; fsync per commit is slow on the NAS
    cursor.close()


def init_db() -> None:
    from app.core.migrations import migrate

    migrate(engine)


def get_session():
    with Session(engine) as session:
        yield session


@event.listens_for(engine, "begin")
def _sqlite_begin(conn):
    conn.exec_driver_sql("BEGIN")
