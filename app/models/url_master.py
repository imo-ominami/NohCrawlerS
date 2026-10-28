from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class UrlMaster(Base):
    __tablename__ = "url_masters"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255)
    )

    url: Mapped[str] = mapped_column(
        String(1000)
    )

    enabled: Mapped[bool]
