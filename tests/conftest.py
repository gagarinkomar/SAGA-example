"""Pytest configuration and fixtures."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.models import Base, User, InventoryItem, PromoCode


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for tests."""
    with PostgresContainer("postgres:16") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def database_url(postgres_container):
    """Get database URL from container."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url):
    """Create SQLAlchemy engine."""
    return create_engine(database_url)


@pytest.fixture
def db_session(engine):
    """Create a new database session for a test."""
    # Полностью пересоздаём схему перед каждым тестом
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def setup_test_data(db_session):
    """Setup test data: users, inventory items, and promo codes."""
    # Create test users
    user1 = User(id=1, name="Иван Иванов", balance=Decimal("1000.00"))
    user2 = User(id=2, name="Петр Петров", balance=Decimal("50.00"))
    db_session.add_all([user1, user2])
    
    # Create inventory items
    item1 = InventoryItem(sku="ITEM001", name="Ноутбук", price=Decimal("100.00"), on_hand=10)
    item2 = InventoryItem(sku="ITEM002", name="Мышка", price=Decimal("100.00"), on_hand=5)
    item3 = InventoryItem(sku="ITEM003", name="Клавиатура", price=Decimal("50.00"), on_hand=0)  # Out of stock
    db_session.add_all([item1, item2, item3])
    
    # Create promo codes
    promo1 = PromoCode(code="DISCOUNT10", remaining_uses=5, discount_amount=Decimal("10.00"))
    promo2 = PromoCode(code="ONETIME", remaining_uses=1, discount_amount=Decimal("20.00"))
    promo3 = PromoCode(code="EXPIRED", remaining_uses=0, discount_amount=Decimal("15.00"))
    db_session.add_all([promo1, promo2, promo3])
    
    db_session.commit()
    
    return {
        "users": [user1, user2],
        "items": [item1, item2, item3],
        "promos": [promo1, promo2, promo3]
    }
