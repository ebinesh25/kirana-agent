from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey,
    CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    brand = Column(Text)
    unit_size = Column(Float)
    unit_type = Column(Text, nullable=False)
    is_loose = Column(Boolean, default=False)
    cost_price = Column(Integer, nullable=False)
    sell_price = Column(Integer, nullable=False)
    mrp = Column(Integer)
    gst_slab = Column(Integer, nullable=False)
    hsn_code = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False, default=0)
    reorder_level = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        CheckConstraint("sell_price >= cost_price", name="ck_sell_above_cost"),
        CheckConstraint("gst_slab IN (0, 5, 12, 18)", name="ck_valid_gst_slab"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    movement_type = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False)
    cost_price = Column(Integer)
    reference = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_number = Column(Text, unique=True, nullable=False)
    status = Column(Text, nullable=False, default="draft")
    chat_id = Column(Text)
    customer_name = Column(Text)
    payment_mode = Column(Text)
    payment_ref = Column(Text)
    subtotal = Column(Integer, default=0)
    total_cgst = Column(Integer, default=0)
    total_sgst = Column(Integer, default=0)
    total_tax = Column(Integer, default=0)
    round_off = Column(Integer, default=0)
    grand_total = Column(Integer, default=0)
    idempotency_key = Column(Text, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finalized_at = Column(DateTime)
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'finalized', 'cancelled')", name="ck_bill_status"),
    )


class BillItem(Base):
    __tablename__ = "bill_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name_snapshot = Column(Text, nullable=False)
    unit_snapshot = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False)
    sell_price = Column(Integer, nullable=False)
    gst_slab = Column(Integer, nullable=False)
    hsn_code = Column(Text, nullable=False)
    cgst_amount = Column(Integer, default=0)
    sgst_amount = Column(Integer, default=0)
    line_total = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class KhataCustomer(Base):
    __tablename__ = "khata_customers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    phone = Column(Text)
    balance = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class KhataTransaction(Base):
    __tablename__ = "khata_transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("khata_customers.id"), nullable=False)
    txn_type = Column(Text, nullable=False)
    amount = Column(Integer, nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id"))
    payment_mode = Column(Text)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        CheckConstraint("txn_type IN ('credit', 'settle')", name="ck_khata_txn_type"),
    )


class OwnerPreference(Base):
    __tablename__ = "owner_preferences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessedUpdate(Base):
    __tablename__ = "processed_updates"
    telegram_update_id = Column(Integer, primary_key=True)
    processed_at = Column(DateTime, default=datetime.utcnow)


class ChatState(Base):
    __tablename__ = "chat_state"
    chat_id = Column(Text, primary_key=True)
    active_bill_id = Column(Integer, ForeignKey("bills.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
