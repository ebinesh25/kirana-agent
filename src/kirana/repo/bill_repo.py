from datetime import datetime
from sqlalchemy import func
from kirana.db.connection import get_session
from kirana.db.models import Bill, BillItem, ChatState


def _bill_to_dict(bill: Bill) -> dict:
    return {
        "id": bill.id,
        "bill_number": bill.bill_number,
        "status": bill.status,
        "chat_id": bill.chat_id,
        "customer_name": bill.customer_name,
        "payment_mode": bill.payment_mode,
        "payment_ref": bill.payment_ref,
        "subtotal": bill.subtotal,
        "total_cgst": bill.total_cgst,
        "total_sgst": bill.total_sgst,
        "total_tax": bill.total_tax,
        "round_off": bill.round_off,
        "grand_total": bill.grand_total,
        "idempotency_key": bill.idempotency_key,
        "created_at": bill.created_at,
        "finalized_at": bill.finalized_at,
    }


def _item_to_dict(item: BillItem) -> dict:
    return {
        "id": item.id,
        "bill_id": item.bill_id,
        "product_id": item.product_id,
        "product_name_snapshot": item.product_name_snapshot,
        "unit_snapshot": item.unit_snapshot,
        "quantity": item.quantity,
        "sell_price": item.sell_price,
        "gst_slab": item.gst_slab,
        "hsn_code": item.hsn_code,
        "cgst_amount": item.cgst_amount,
        "sgst_amount": item.sgst_amount,
        "line_total": item.line_total,
        "created_at": item.created_at,
    }


def next_bill_number() -> str:
    from sqlalchemy import func
    from kirana.db.connection import get_session
    from kirana.db.models import Bill
    with get_session() as session:
        last = session.query(func.max(Bill.bill_number)).scalar()
        if last and last.startswith("INV-"):
            num = int(last.split("-")[1])
            return f"INV-{num + 1:04d}"
        return "INV-0001"


def create_bill(chat_id: str, customer_name: str | None = None) -> dict:
    with get_session() as session:
        bill = Bill(
            bill_number=next_bill_number(),
            status="draft",
            chat_id=chat_id,
            customer_name=customer_name,
        )
        session.add(bill)
        session.flush()
        return _bill_to_dict(bill)


def get_bill(bill_id: int) -> dict | None:
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return None
        result = _bill_to_dict(bill)
        result["items"] = [_item_to_dict(i) for i in bill.items]
        return result


def get_active_bill(chat_id: str) -> dict | None:
    with get_session() as session:
        cs = session.query(ChatState).filter(ChatState.chat_id == chat_id).first()
        if not cs or not cs.active_bill_id:
            return None
        return get_bill(cs.active_bill_id)


def set_active_bill(chat_id: str, bill_id: int):
    with get_session() as session:
        cs = session.query(ChatState).filter(ChatState.chat_id == chat_id).first()
        if cs:
            cs.active_bill_id = bill_id
        else:
            session.add(ChatState(chat_id=chat_id, active_bill_id=bill_id))


def add_item(
    bill_id: int,
    product_id: int,
    product_name_snapshot: str,
    unit_snapshot: str,
    quantity: float,
    sell_price: int,
    gst_slab: int,
    hsn_code: str,
) -> dict:
    with get_session() as session:
        item = BillItem(
            bill_id=bill_id,
            product_id=product_id,
            product_name_snapshot=product_name_snapshot,
            unit_snapshot=unit_snapshot,
            quantity=quantity,
            sell_price=sell_price,
            gst_slab=gst_slab,
            hsn_code=hsn_code,
        )
        session.add(item)
        session.flush()
        return _item_to_dict(item)


def update_item(bill_id: int, product_id: int, new_qty: float) -> dict | None:
    with get_session() as session:
        item = (
            session.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if not item:
            return None
        item.quantity = new_qty
        session.flush()
        return _item_to_dict(item)


def remove_item(bill_id: int, product_id: int) -> dict | None:
    with get_session() as session:
        item = (
            session.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if not item:
            return None
        result = _item_to_dict(item)
        session.delete(item)
        return result


def get_items(bill_id: int) -> list[dict]:
    with get_session() as session:
        items = session.query(BillItem).filter(BillItem.bill_id == bill_id).all()
        return [_item_to_dict(i) for i in items]


def finalize(
    bill_id: int,
    payment_mode: str,
    payment_ref: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).one()
        bill.status = "finalized"
        bill.payment_mode = payment_mode
        bill.payment_ref = payment_ref
        if idempotency_key:
            bill.idempotency_key = idempotency_key
        bill.finalized_at = datetime.utcnow()
        session.flush()
        return _bill_to_dict(bill)


def cancel(bill_id: int) -> dict:
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).one()
        bill.status = "cancelled"
        session.flush()
        return _bill_to_dict(bill)
