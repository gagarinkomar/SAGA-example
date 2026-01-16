import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import PromoCode, PromoApplication

logger = logging.getLogger(__name__)


class DiscountsService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_discount(self, promo_code: str | None, base_amount: Decimal) -> Decimal:
        if not promo_code:
            return Decimal("0")
        promo = self.db.query(PromoCode).filter(PromoCode.code == promo_code).first()
        if not promo or promo.remaining_uses <= 0:
            return Decimal("0")
        return promo.discount_amount

    def reserve_promo_use(self, order_id: int, promo_code: str) -> None:
        promo = self.db.query(PromoCode).filter(PromoCode.code == promo_code).first()
        if not promo:
            raise ValueError(f"Promo code {promo_code} not found")
        if promo.remaining_uses <= 0:
            raise ValueError(f"Promo code {promo_code} has no remaining uses")
        promo.remaining_uses -= 1
        self.db.add(PromoApplication(order_id=order_id, code=promo_code, status="APPLIED"))
        self.db.flush()

    def release_promo_use(self, order_id: int, promo_code: str) -> None:
        promo = self.db.query(PromoCode).filter(PromoCode.code == promo_code).first()
        if not promo:
            return
        promo.remaining_uses += 1
        application = self.db.query(PromoApplication).filter(
            PromoApplication.order_id == order_id, PromoApplication.code == promo_code
        ).first()
        if application:
            application.status = "CANCELLED"
        self.db.flush()
