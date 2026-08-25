"""SQLAlchemy declarative base used by the production application."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

