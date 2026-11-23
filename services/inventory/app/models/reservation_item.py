
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint
from app.db.base import Base


class StockReservationItem(Base):
    __tablename__ = "stock_reservation_items"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_reservation_item_quantity_positive",
        ),
        UniqueConstraint(
    "reservation_id",
    "inventory_item_id",
    name="uq_reservation_inventory_item",
),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stock_reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reservation: Mapped["StockReservation"] = relationship(
        back_populates="items",
    )
