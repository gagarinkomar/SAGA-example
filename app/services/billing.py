import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import User, Payment

logger = logging.getLogger(__name__)


class BillingService:
    def __init__(self, db: Session):
        self.db = db

    def charge_user_balance(self, order_id: int, user_id: int, amount: Decimal) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        if user.balance < amount:
            raise ValueError(f"Insufficient balance for user {user_id}. Balance: {user.balance}, Required: {amount}")
        user.balance -= amount
        self.db.add(Payment(order_id=order_id, user_id=user_id, amount=amount, status="CHARGED"))
        self.db.flush()

    def refund_payment(self, order_id: int, user_id: int, amount: Decimal) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        user.balance += amount
        payment = self.db.query(Payment).filter(Payment.order_id == order_id, Payment.user_id == user_id).first()
        if payment:
            payment.status = "REFUNDED"
        self.db.flush()
