from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Alembic sees metadata
def import_models() -> None:
    from app import models  # noqa: F401
