"""Tests for Order Saga orchestration."""
import logging
from decimal import Decimal

import pytest

from app.models import Order, User, InventoryItem, PromoCode, SagaStep
from app.saga import OrderSaga

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_successful_order_without_promo(db_session, setup_test_data):
    """Test successful order without promo code."""
    logging.info("\n=== TEST: Successful order without promo ===")
    
    # Create order
    order = Order(
        user_id=1,
        promo_code=None,
        sku="ITEM001",
        qty=2,
        base_amount=Decimal("200.00"),
        discount_amount=Decimal("0.00"),
        final_amount=Decimal("200.00"),
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Execute saga
    saga = OrderSaga(db_session)
    success = saga.execute(order.id)
    
    # Assertions
    assert success is True
    
    assert order.status == "CONFIRMED"
    
    # Check inventory
    item = db_session.query(InventoryItem).filter(InventoryItem.sku == "ITEM001").first()
    assert item.on_hand == 8  # 10 - 2
    
    # Check balance
    user = db_session.query(User).filter(User.id == 1).first()
    assert user.balance == Decimal("800.00")  # 1000 - 200
    
    # Check saga steps
    steps = db_session.query(SagaStep).filter(SagaStep.order_id == order.id).all()
    assert len(steps) == 3  # ReserveInventory, ChargeUserBalance, FinalizeOrder
    assert all(step.status == "COMPLETED" for step in steps)
    
    logging.info("✓ Order completed successfully")


def test_successful_order_with_promo(db_session, setup_test_data):
    """Test successful order with promo code."""
    logging.info("\n=== TEST: Successful order with promo code ===")
    
    # Create order
    order = Order(
        user_id=1,
        promo_code="DISCOUNT10",
        sku="ITEM001",
        qty=1,
        base_amount=Decimal("100.00"),
        discount_amount=Decimal("10.00"),
        final_amount=Decimal("90.00"),
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Get initial promo uses
    promo = db_session.query(PromoCode).filter(PromoCode.code == "DISCOUNT10").first()
    initial_uses = promo.remaining_uses
    
    # Execute saga
    saga = OrderSaga(db_session)
    success = saga.execute(order.id)
    
    # Assertions
    assert success is True
    
    assert order.status == "CONFIRMED"
    
    # Check promo code usage
    assert promo.remaining_uses == initial_uses - 1
    
    # Check inventory
    item = db_session.query(InventoryItem).filter(InventoryItem.sku == "ITEM001").first()
    assert item.on_hand == 9  # 10 - 1
    
    # Check balance (discount applied)
    user = db_session.query(User).filter(User.id == 1).first()
    assert user.balance == Decimal("910.00")  # 1000 - 90
    
    logging.info("✓ Order with promo completed successfully")


def test_fail_on_insufficient_promo_uses(db_session, setup_test_data):
    """Test failure when promo code has no remaining uses."""
    logging.info("\n=== TEST: Fail on insufficient promo uses ===")
    
    # Create order with expired promo
    order = Order(
        user_id=1,
        promo_code="EXPIRED",
        sku="ITEM001",
        qty=1,
        base_amount=Decimal("100.00"),
        discount_amount=Decimal("15.00"),
        final_amount=Decimal("85.00"),
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Execute saga (should fail)
    saga = OrderSaga(db_session)
    success = saga.execute(order.id)
    
    # Assertions
    assert success is False
    
    assert order.status == "FAILED"
    
    # Check that inventory was NOT reserved
    item = db_session.query(InventoryItem).filter(InventoryItem.sku == "ITEM001").first()
    assert item.on_hand == 10  # Unchanged
    
    # Check that balance was NOT charged
    user = db_session.query(User).filter(User.id == 1).first()
    assert user.balance == Decimal("1000.00")  # Unchanged
    
    # Check saga steps
    steps = db_session.query(SagaStep).filter(SagaStep.order_id == order.id).all()
    failed_step = [s for s in steps if s.status == "FAILED"]
    assert len(failed_step) == 1
    assert failed_step[0].step_name == "ReservePromoUse"
    
    logging.info("✓ Correctly failed on insufficient promo uses")


def test_fail_on_insufficient_inventory(db_session, setup_test_data):
    """Test failure and compensation when inventory is insufficient."""
    logging.info("\n=== TEST: Fail on insufficient inventory ===")
    
    # Create order
    order = Order(
        user_id=1,
        promo_code="DISCOUNT10",
        sku="ITEM001",
        qty=20,  # More than available (10)
        base_amount=Decimal("2000.00"),
        discount_amount=Decimal("10.00"),
        final_amount=Decimal("1990.00"),
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Get initial promo uses
    promo = db_session.query(PromoCode).filter(PromoCode.code == "DISCOUNT10").first()
    initial_uses = promo.remaining_uses
    
    # Execute saga (should fail)
    saga = OrderSaga(db_session)
    success = saga.execute(order.id)
    
    # Assertions
    assert success is False
    
    assert order.status == "FAILED"
    
    # Check that promo was COMPENSATED (released)
    assert promo.remaining_uses == initial_uses  # Restored
    
    # Check inventory unchanged
    item = db_session.query(InventoryItem).filter(InventoryItem.sku == "ITEM001").first()
    assert item.on_hand == 10  # Unchanged
    
    # Check balance unchanged
    user = db_session.query(User).filter(User.id == 1).first()
    assert user.balance == Decimal("1000.00")  # Unchanged
    
    # Check compensation step
    steps = db_session.query(SagaStep).filter(SagaStep.order_id == order.id).all()
    compensation_steps = [s for s in steps if "Compensate" in s.step_name]
    assert len(compensation_steps) == 1
    assert compensation_steps[0].step_name == "Compensate_ReservePromoUse"
    
    logging.info("✓ Correctly compensated promo use after inventory failure")


def test_fail_on_insufficient_balance(db_session, setup_test_data):
    """Test failure and compensation when user balance is insufficient."""
    logging.info("\n=== TEST: Fail on insufficient balance ===")
    
    # Create order with user who has low balance
    order = Order(
        user_id=2,  # User with balance 50
        promo_code="DISCOUNT10",
        sku="ITEM002",
        qty=2,
        base_amount=Decimal("200.00"),
        discount_amount=Decimal("10.00"),
        final_amount=Decimal("190.00"),  # More than user's balance
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Get initial states
    promo = db_session.query(PromoCode).filter(PromoCode.code == "DISCOUNT10").first()
    initial_promo_uses = promo.remaining_uses
    
    item = db_session.query(InventoryItem).filter(InventoryItem.sku == "ITEM002").first()
    initial_inventory = item.on_hand
    
    # Execute saga (should fail)
    saga = OrderSaga(db_session)
    success = saga.execute(order.id)
    
    # Assertions
    assert success is False
    
    assert order.status == "FAILED"
    
    # Check that promo was COMPENSATED
    assert promo.remaining_uses == initial_promo_uses  # Restored
    
    # Check that inventory was COMPENSATED
    assert item.on_hand == initial_inventory  # Restored
    
    # Check balance unchanged
    user = db_session.query(User).filter(User.id == 2).first()
    assert user.balance == Decimal("50.00")  # Unchanged
    
    # Check compensation steps
    steps = db_session.query(SagaStep).filter(SagaStep.order_id == order.id).all()
    compensation_steps = [s for s in steps if "Compensate" in s.step_name]
    assert len(compensation_steps) == 2  # Compensate inventory and promo
    
    logging.info("✓ Correctly compensated inventory and promo after balance failure")


def test_artificial_failure_at_finalize(db_session, setup_test_data):
    """Test artificial failure at FinalizeOrder step to demonstrate full compensation."""
    logging.info("\n=== TEST: Artificial failure at FinalizeOrder ===")
    
    # Create order
    order = Order(
        user_id=1,
        promo_code="DISCOUNT10",
        sku="ITEM001",
        qty=1,
        base_amount=Decimal("100.00"),
        discount_amount=Decimal("10.00"),
        final_amount=Decimal("90.00"),
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Get initial states
    promo = db_session.query(PromoCode).filter(PromoCode.code == "DISCOUNT10").first()
    initial_promo_uses = promo.remaining_uses
    
    item = db_session.query(InventoryItem).filter(InventoryItem.sku == "ITEM001").first()
    initial_inventory = item.on_hand
    
    user = db_session.query(User).filter(User.id == 1).first()
    initial_balance = user.balance
    
    # Execute saga with artificial failure at FinalizeOrder
    saga = OrderSaga(db_session)
    success = saga.execute(order.id, fail_at_step="FinalizeOrder")
    
    # Assertions
    assert success is False
    
    assert order.status == "FAILED"
    
    # Check that ALL resources were COMPENSATED
    assert promo.remaining_uses == initial_promo_uses  # Restored
    
    assert item.on_hand == initial_inventory  # Restored
    
    assert user.balance == initial_balance  # Restored
    
    # Check compensation steps - should have 3 compensations
    steps = db_session.query(SagaStep).filter(SagaStep.order_id == order.id).all()
    compensation_steps = [s for s in steps if "Compensate" in s.step_name]
    assert len(compensation_steps) == 3  # All three steps compensated
    
    compensation_names = [s.step_name for s in compensation_steps]
    assert "Compensate_ChargeUserBalance" in compensation_names
    assert "Compensate_ReserveInventory" in compensation_names
    assert "Compensate_ReservePromoUse" in compensation_names
    
    logging.info("✓ All compensations executed successfully after late-stage failure")


def test_order_without_promo_succeeds(db_session, setup_test_data):
    """Test that order without promo code skips promo step."""
    logging.info("\n=== TEST: Order without promo skips promo step ===")
    
    # Create order without promo
    order = Order(
        user_id=1,
        promo_code=None,
        sku="ITEM002",
        qty=1,
        base_amount=Decimal("50.00"),
        discount_amount=Decimal("0.00"),
        final_amount=Decimal("50.00"),
        status="PENDING"
    )
    db_session.add(order)
    db_session.commit()
    
    # Execute saga
    saga = OrderSaga(db_session)
    success = saga.execute(order.id)
    
    # Assertions
    assert success is True
    
    # Check that ReservePromoUse step was NOT executed
    steps = db_session.query(SagaStep).filter(SagaStep.order_id == order.id).all()
    step_names = [s.step_name for s in steps]
    assert "ReservePromoUse" not in step_names
    assert "ReserveInventory" in step_names
    assert "ChargeUserBalance" in step_names
    assert "FinalizeOrder" in step_names
    
    logging.info("✓ Order without promo correctly skipped promo step")
