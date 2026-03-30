from __future__ import annotations

import os
from typing import Generator, Optional

try:
    import streamlit as st
except ModuleNotFoundError:  # Backend (FastAPI) n'utilise pas Streamlit
    st = None  # type: ignore

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_SQLITE_URL = "sqlite:///./glutify.db"


def _get_database_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    if st is not None:
        try:
            return st.secrets["DATABASE_URL"]
        except Exception:
            pass
    return DEFAULT_SQLITE_URL


def _normalize(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[1]:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize(_get_database_url())

connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_user_profile_schema() -> None:
    inspector = inspect(engine)
    try:
        columns = [
            col["name"] for col in inspector.get_columns("user_profiles")
        ]
    except Exception:
        return
    if "password" in columns:
        return
    ddl = (
        "ALTER TABLE user_profiles ADD COLUMN password VARCHAR(255) DEFAULT ''"
    )
    if engine.dialect.name == "sqlite":
        ddl = "ALTER TABLE user_profiles ADD COLUMN password TEXT DEFAULT ''"
    with engine.begin() as conn:
        conn.execute(text(ddl))


def ensure_history_columns() -> None:
    inspector = inspect(engine)
    targets = [
        "analysis_logs",
        "recipe_logs",
        "favorite_recipes",
    ]
    for table in targets:
        try:
            columns = [col["name"] for col in inspector.get_columns(table)]
        except Exception:
            continue
        if "user_id" not in columns:
            ddl = f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"
            if engine.dialect.name == "sqlite":
                ddl = f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"
            with engine.begin() as conn:
                conn.execute(text(ddl))
        if table == "analysis_logs" and "image_url" not in columns:
            ddl_img = "ALTER TABLE analysis_logs ADD COLUMN image_url VARCHAR(512)"
            if engine.dialect.name == "sqlite":
                ddl_img = "ALTER TABLE analysis_logs ADD COLUMN image_url TEXT"
            with engine.begin() as conn:
                conn.execute(text(ddl_img))
