"""SQLAlchemy engine / session wiring."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite ignores foreign keys unless asked, per connection.
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to tables that already shipped. `create_all` creates missing
# tables but never alters existing ones, so these are applied by hand.
# This is a stopgap for local development — move to Alembic before deploying.
# (table, column, type, backfill value or None)
#
# Types must be spelled so both backends accept them. Notably a boolean
# default cannot be written as 0: SQLite allows it, Postgres raises
# DatatypeMismatch. Backfills are applied as a separate UPDATE with a
# dialect-appropriate literal instead of a DEFAULT clause.
_ADDED_COLUMNS: list[tuple[str, str, str, str | None]] = [
    ("profiles", "user_id", "INTEGER", None),
    ("users", "email", "VARCHAR(240)", None),
    ("users", "email_verified", "BOOLEAN", "false"),
    ("profiles", "phone", "VARCHAR(24)", "empty"),
    ("profiles", "college", "VARCHAR(200)", "empty"),
    ("profiles", "degree", "VARCHAR(80)", "empty"),
    ("profiles", "branch", "VARCHAR(120)", "empty"),
    ("profiles", "year_of_study", "VARCHAR(40)", "empty"),
    ("profiles", "graduation_year", "VARCHAR(8)", "empty"),
    ("profiles", "registration_number", "VARCHAR(60)", "empty"),
    ("profiles", "city", "VARCHAR(120)", "empty"),
    ("profiles", "github_url", "VARCHAR(300)", "empty"),
    ("profiles", "linkedin_url", "VARCHAR(300)", "empty"),
    ("profiles", "portfolio_url", "VARCHAR(300)", "empty"),
    ("profiles", "resume_url", "VARCHAR(300)", "empty"),
    ("profiles", "bio", "TEXT", "empty"),
    ("profiles", "experience", "TEXT", "empty"),
    ("profiles", "achievements", "TEXT", "empty"),
    ("profiles", "team_name", "VARCHAR(120)", "empty"),
    ("bookmarks", "status", "VARCHAR(20)", "saved"),
    ("internship_bookmarks", "status", "VARCHAR(20)", "saved"),
    ("users", "oauth_provider", "VARCHAR(20)", "empty"),
    ("users", "oauth_subject", "VARCHAR(200)", "empty"),
]

#: How each backend spells a false literal.
_FALSE_LITERAL = {"sqlite": "0", "postgresql": "FALSE"}

# Schema changes beyond adding a column. SQLite ignores VARCHAR lengths and
# cannot drop an index created by a UNIQUE constraint the same way, so each
# entry names the dialects it applies to.
_SCHEMA_FIXES: list[tuple[str, str]] = [
    # sent_to held a phone number (24 chars) before codes moved to email.
    ("postgresql", "ALTER TABLE otp_codes ALTER COLUMN sent_to TYPE VARCHAR(240)"),
    # One inbox may now hold several accounts, so email must not be unique.
    ("postgresql", "DROP INDEX IF EXISTS ix_users_email"),
    ("postgresql", "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"),
    ("sqlite", "DROP INDEX IF EXISTS ix_users_email"),
    ("sqlite", "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"),
    # OAuth lookups are provider+subject, not a column either one indexes alone.
    ("postgresql", "CREATE INDEX IF NOT EXISTS ix_users_oauth ON users (oauth_provider, oauth_subject)"),
    ("sqlite", "CREATE INDEX IF NOT EXISTS ix_users_oauth ON users (oauth_provider, oauth_subject)"),
]


def _apply_schema_fixes() -> None:
    """Run the non-additive migrations, ignoring ones already applied."""
    from sqlalchemy import text

    dialect = engine.dialect.name
    for target, statement in _SCHEMA_FIXES:
        if target != dialect:
            continue
        try:
            with engine.begin() as connection:
                connection.execute(text(statement))
        except Exception as exc:  # noqa: BLE001 - best effort, already-applied is fine
            import logging

            logging.getLogger(__name__).debug("schema fix skipped (%s): %s", statement, exc)


def _apply_pending_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    dialect = engine.dialect.name

    with engine.begin() as connection:
        for table, column, ddl_type, backfill in _ADDED_COLUMNS:
            if table not in existing_tables:
                continue
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue

            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))

            if backfill == "false":
                literal = _FALSE_LITERAL.get(dialect, "FALSE")
                connection.execute(
                    text(f"UPDATE {table} SET {column} = {literal} WHERE {column} IS NULL")
                )
            elif backfill == "empty":
                connection.execute(
                    text(f"UPDATE {table} SET {column} = '' WHERE {column} IS NULL")
                )
            elif backfill is not None:
                # Any other string is a literal value, bound rather than
                # interpolated even though it only ever comes from this file.
                connection.execute(
                    text(f"UPDATE {table} SET {column} = :val WHERE {column} IS NULL"),
                    {"val": backfill},
                )


def init_db() -> None:
    from . import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=engine)
    _apply_pending_columns()
    _apply_schema_fixes()
