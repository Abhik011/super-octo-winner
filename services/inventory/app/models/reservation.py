import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class StockReservation(Base):
    __tablename__ = "stock_reservations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'confirmed', 'released', 'expired')",
            name="ck_reservation_status",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_reservation_idempotency_key",
        ),
      
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    request_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    items: Mapped[list["StockReservationItem"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
    )
