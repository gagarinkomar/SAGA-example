"""Скрипт для добавления тестовых данных в базу данных."""
from decimal import Decimal
from app.db import SessionLocal, engine
from app.models import Base, User, InventoryItem, PromoCode

def seed_data():
    """Добавить тестовые данные в БД."""
    # Создаём таблицы если их нет
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Проверяем, есть ли уже данные
        if db.query(User).count() > 0:
            print("Данные уже существуют. Очищаю таблицы...")
            # Очищаем таблицы в правильном порядке (из-за внешних ключей)
            db.execute("DELETE FROM saga_steps")
            db.execute("DELETE FROM promo_applications")
            db.execute("DELETE FROM inventory_reservations")
            db.execute("DELETE FROM payments")
            db.execute("DELETE FROM orders")
            db.execute("DELETE FROM promo_codes")
            db.execute("DELETE FROM inventory_items")
            db.execute("DELETE FROM users")
            db.commit()
            print("Таблицы очищены")
        
        # Создаём пользователей
        users = [
            User(id=1, name="Иван Иванов", balance=Decimal("100000.00")),
            User(id=2, name="Петр Петров", balance=Decimal("5000.00")),
            User(id=3, name="Анна Смирнова", balance=Decimal("500000.00")),
        ]
        db.add_all(users)
        print("Добавлено пользователей: 3")
        
        # Создаём товары
        items = [
            InventoryItem(sku="LAPTOP-DELL", name="Ноутбук Dell XPS 13", price=Decimal("85000.00"), on_hand=10),
            InventoryItem(sku="MOUSE-WIRELESS", name="Беспроводная мышь Logitech", price=Decimal("1500.00"), on_hand=25),
            InventoryItem(sku="LAPTOP-MAC", name="MacBook Pro 16", price=Decimal("250000.00"), on_hand=3),
            InventoryItem(sku="PHONE-IPHONE", name="iPhone 15 Pro", price=Decimal("120000.00"), on_hand=0),  # Нет в наличии
            InventoryItem(sku="KEYBOARD", name="Механическая клавиатура", price=Decimal("8000.00"), on_hand=15),
        ]
        db.add_all(items)
        print("Добавлено товаров: 5")
        
        # Создаём промокоды
        promos = [
            PromoCode(code="DISCOUNT10", remaining_uses=5, discount_amount=Decimal("1000.00")),
            PromoCode(code="BIGDEAL", remaining_uses=2, discount_amount=Decimal("10000.00")),
            PromoCode(code="ONETIME", remaining_uses=1, discount_amount=Decimal("5000.00")),
            PromoCode(code="EXPIRED", remaining_uses=0, discount_amount=Decimal("2000.00")),  # Истек
        ]
        db.add_all(promos)
        print("Добавлено промокодов: 4")
        
        db.commit()
        
        print("\n" + "="*50)
        print("Тестовые данные успешно добавлены")
        print("="*50)
        
        print("\nСводка:")
        print("Пользователи:")
        for u in users:
            print(f"- {u.name}: {u.balance}₽")
        
        print("\nТовары:")
        for i in items:
            stock_status = "IN_STOCK" if i.on_hand > 0 else "OUT_OF_STOCK"
            print(f"- [{stock_status}] {i.name}: {i.price}₽ (остаток: {i.on_hand})")
        
        print("\nПромокоды:")
        for p in promos:
            print(f"- {p.code}: -{p.discount_amount}₽ (использований: {p.remaining_uses})")
        
        print("\nЗапустите приложение: uv run uvicorn app.main:app --reload")
        print("Откройте: http://localhost:8000")
        
    except Exception as e:
        db.rollback()
        print(f"Ошибка: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
