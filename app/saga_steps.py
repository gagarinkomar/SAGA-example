from decimal import Decimal
from sqlalchemy.orm import Session
from app.saga_step import SagaStepBase
from app.services.discounts import DiscountsService
from app.services.inventory import InventoryService
from app.services.billing import BillingService
from app.models import Order


class ReservePromoUseStep(SagaStepBase):
    def __init__(self, db: Session, order_id: int, promo_code: str):
        super().__init__(db, order_id)
        self.promo_code = promo_code
        self.service = DiscountsService(db)

    def execute(self) -> None:
        self.service.reserve_promo_use(self.order_id, self.promo_code)

    def compensate(self) -> None:
        self.service.release_promo_use(self.order_id, self.promo_code)

    def get_name(self) -> str:
        return "ReservePromoUse"


class ReserveInventoryStep(SagaStepBase):
    def __init__(self, db: Session, order_id: int, sku: str, qty: int):
        super().__init__(db, order_id)
        self.sku = sku
        self.qty = qty
        self.service = InventoryService(db)

    def execute(self) -> None:
        self.service.reserve_inventory(self.order_id, self.sku, self.qty)

    def compensate(self) -> None:
        self.service.release_inventory(self.order_id, self.sku, self.qty)

    def get_name(self) -> str:
        return "ReserveInventory"


class ChargeUserBalanceStep(SagaStepBase):
    def __init__(self, db: Session, order_id: int, user_id: int, amount: Decimal):
        super().__init__(db, order_id)
        self.user_id = user_id
        self.amount = amount
        self.service = BillingService(db)

    def execute(self) -> None:
        self.service.charge_user_balance(self.order_id, self.user_id, self.amount)

    def compensate(self) -> None:
        self.service.refund_payment(self.order_id, self.user_id, self.amount)

    def get_name(self) -> str:
        return "ChargeUserBalance"


class FinalizeOrderStep(SagaStepBase):
    def __init__(self, db: Session, order_id: int):
        super().__init__(db, order_id)

    def execute(self) -> None:
        order = self.db.query(Order).filter(Order.id == self.order_id).first()
        if order:
            order.status = "CONFIRMED"
            self.db.flush()

    def compensate(self) -> None:
        pass

    def get_name(self) -> str:
        return "FinalizeOrder"
