from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    balance = Column(Numeric(15, 2), nullable=False, default=0)

    payments = relationship("Payment", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, balance={self.balance})>"


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    sku = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Numeric(15, 2), nullable=False)
    on_hand = Column(Integer, nullable=False, default=0)

    reservations = relationship("InventoryReservation", back_populates="item")

    def __repr__(self):
        return f"<InventoryItem(sku={self.sku}, name={self.name}, price={self.price}, on_hand={self.on_hand})>"


class PromoCode(Base):
    __tablename__ = "promo_codes"

    code = Column(String(50), primary_key=True)
    remaining_uses = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Numeric(15, 2), nullable=False)

    applications = relationship("PromoApplication", back_populates="promo")

    def __repr__(self):
        return f"<PromoCode(code={self.code}, remaining_uses={self.remaining_uses}, discount={self.discount_amount})>"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    promo_code = Column(String(50), ForeignKey("promo_codes.code"), nullable=True)
    sku = Column(String(50), ForeignKey("inventory_items.sku"), nullable=False)
    qty = Column(Integer, nullable=False)
    base_amount = Column(Numeric(15, 2), nullable=False)
    discount_amount = Column(Numeric(15, 2), nullable=False, default=0)
    final_amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, CONFIRMED, FAILED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    promo = relationship("PromoCode")
    item = relationship("InventoryItem")
    saga_steps = relationship("SagaStep", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id}, status={self.status})>"


class SagaStep(Base):
    __tablename__ = "saga_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    step_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # STARTED, COMPLETED, FAILED, COMPENSATED
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="saga_steps")

    def __repr__(self):
        return f"<SagaStep(order_id={self.order_id}, step={self.step_name}, status={self.status})>"


class PromoApplication(Base):
    __tablename__ = "promo_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    code = Column(String(50), ForeignKey("promo_codes.code"), nullable=False)
    status = Column(String(20), nullable=False)  # APPLIED, CANCELLED

    order = relationship("Order")
    promo = relationship("PromoCode", back_populates="applications")

    def __repr__(self):
        return f"<PromoApplication(order_id={self.order_id}, code={self.code}, status={self.status})>"


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    sku = Column(String(50), ForeignKey("inventory_items.sku"), nullable=False)
    qty = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)  # RESERVED, RELEASED

    order = relationship("Order")
    item = relationship("InventoryItem", back_populates="reservations")

    def __repr__(self):
        return f"<InventoryReservation(order_id={self.order_id}, sku={self.sku}, qty={self.qty}, status={self.status})>"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), nullable=False)  # CHARGED, REFUNDED

    order = relationship("Order")
    user = relationship("User", back_populates="payments")

    def __repr__(self):
        return f"<Payment(order_id={self.order_id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"
