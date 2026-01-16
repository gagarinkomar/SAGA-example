import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import Order
from app.saga_step import SagaStepBase
from app.saga_steps import ReservePromoUseStep, ReserveInventoryStep, ChargeUserBalanceStep, FinalizeOrderStep

logger = logging.getLogger(__name__)


class SagaException(Exception):
    pass


class OrderSaga:
    def __init__(self, db: Session):
        self.db = db

    def execute(self, order_id: int, fail_at_step: Optional[str] = None) -> bool:
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        logger.info(f"Starting saga for order {order_id}")
        
        steps: List[SagaStepBase] = []
        if order.promo_code:
            steps.append(ReservePromoUseStep(self.db, order_id, order.promo_code))
        steps.append(ReserveInventoryStep(self.db, order_id, order.sku, order.qty))
        steps.append(ChargeUserBalanceStep(self.db, order_id, order.user_id, order.final_amount))
        steps.append(FinalizeOrderStep(self.db, order_id))
        
        completed_steps: List[SagaStepBase] = []
        
        try:
            for step in steps:
                if fail_at_step == step.get_name():
                    raise SagaException(f"Artificial failure at step {step.get_name()}")
                step.run()
                completed_steps.append(step)
            logger.info(f"Saga completed for order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Saga failed for order {order_id}: {e}")
            self.db.rollback()
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = "FAILED"
            self.db.commit()
            self._compensate(completed_steps)
            return False

    def _compensate(self, completed_steps: List[SagaStepBase]) -> None:
        order_id = completed_steps[0].order_id if completed_steps else None
        if order_id:
            logger.info(f"Starting compensation for order {order_id}")
        for step in reversed(completed_steps):
            step.run_compensation()
        if order_id:
            logger.info(f"Compensation completed for order {order_id}")
