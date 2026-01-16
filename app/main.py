import logging
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, SagaStep, User, InventoryItem, PromoCode
from app.saga import OrderSaga
from app.services.discounts import DiscountsService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastAPI(title="Saga Order Management")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).all()
    items = db.query(InventoryItem).all()
    return templates.TemplateResponse("index.html", {"request": request, "users": users, "items": items})


@app.post("/orders", response_class=HTMLResponse)
async def create_order(
    request: Request,
    user_id: int = Form(...),
    sku: str = Form(...),
    qty: int = Form(...),
    promo_code: Optional[str] = Form(None),
    fail_at_step: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        promo_code = promo_code or None
        fail_at_step = fail_at_step or None

        if qty <= 0:
            raise HTTPException(status_code=400, detail="Количество товара должно быть больше 0")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь {user_id} не найден")

        item = db.query(InventoryItem).filter(InventoryItem.sku == sku).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Товар {sku} не найден")
        
        if promo_code:
            promo = db.query(PromoCode).filter(PromoCode.code == promo_code).first()
            if not promo:
                raise HTTPException(status_code=400, detail=f"Промокод '{promo_code}' не найден")
            if promo.remaining_uses <= 0:
                raise HTTPException(status_code=400, detail=f"Промокод '{promo_code}' исчерпан")

        base_amount = item.price * qty
        discount_amount = DiscountsService(db).calculate_discount(promo_code, base_amount)
        final_amount = base_amount - discount_amount

        order = Order(
            user_id=user_id, sku=sku, qty=qty,
            base_amount=base_amount, discount_amount=discount_amount, final_amount=final_amount,
            promo_code=promo_code, status="PENDING"
        )
        db.add(order)
        db.commit()

        saga = OrderSaga(db)
        saga.execute(order.id, fail_at_step)

        saga_steps = db.query(SagaStep).filter(SagaStep.order_id == order.id).order_by(SagaStep.started_at).all()
        return templates.TemplateResponse("order_success.html", {
            "request": request, "order": order, "saga_steps": saga_steps
        })

    except HTTPException as e:
        db.rollback()
        users = db.query(User).all()
        items = db.query(InventoryItem).all()
        return templates.TemplateResponse("index.html", {
            "request": request, "users": users, "items": items, "error": e.detail
        }, status_code=e.status_code)
    
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating order: {e}", exc_info=True)
        users = db.query(User).all()
        items = db.query(InventoryItem).all()
        return templates.TemplateResponse("index.html", {
            "request": request, "users": users, "items": items, "error": f"Ошибка сервера: {str(e)}"
        }, status_code=500)


@app.get("/orders/{order_id}", response_class=HTMLResponse)
async def get_order(request: Request, order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    saga_steps = db.query(SagaStep).filter(SagaStep.order_id == order_id).order_by(SagaStep.started_at).all()
    return templates.TemplateResponse("order_success.html", {
        "request": request, "order": order, "saga_steps": saga_steps
    })


@app.get("/health")
async def health_check():
    return {"status": "ok"}
