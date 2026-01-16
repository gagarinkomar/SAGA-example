import logging
from sqlalchemy.orm import Session
from app.models import InventoryItem, InventoryReservation

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self, db: Session):
        self.db = db

    def reserve_inventory(self, order_id: int, sku: str, qty: int) -> None:
        item = self.db.query(InventoryItem).filter(InventoryItem.sku == sku).first()
        if not item:
            raise ValueError(f"Item {sku} not found in inventory")
        if item.on_hand < qty:
            raise ValueError(f"Insufficient inventory for {sku}. Available: {item.on_hand}, Requested: {qty}")
        item.on_hand -= qty
        self.db.add(InventoryReservation(order_id=order_id, sku=sku, qty=qty, status="RESERVED"))
        self.db.flush()

    def release_inventory(self, order_id: int, sku: str, qty: int) -> None:
        item = self.db.query(InventoryItem).filter(InventoryItem.sku == sku).first()
        if not item:
            return
        item.on_hand += qty
        reservation = self.db.query(InventoryReservation).filter(
            InventoryReservation.order_id == order_id, InventoryReservation.sku == sku
        ).first()
        if reservation:
            reservation.status = "RELEASED"
        self.db.flush()
