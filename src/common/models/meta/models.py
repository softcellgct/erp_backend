from typing import List
from uuid import UUID
from components.db.base_model import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey

class Religion(Base):
    __tablename__ = "religions"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Community(Base):
    __tablename__ = "communities"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    castes: Mapped[List["Caste"]] = relationship(
        "Caste", back_populates="community", lazy="select"
    )


class Caste(Base):
    __tablename__ = "castes"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    community_id: Mapped[UUID] = mapped_column(
        ForeignKey("communities.id"),
        nullable=False,
        index=True,
    )

    community: Mapped["Community"] = relationship(
        "Community", back_populates="castes", lazy="select"
    )
