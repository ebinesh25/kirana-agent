from kirana.db.connection import get_session
from kirana.db.models import KhataCustomer, KhataTransaction


def _customer_to_dict(customer: KhataCustomer) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "balance": customer.balance,
        "created_at": customer.created_at,
    }


def _txn_to_dict(txn: KhataTransaction) -> dict:
    return {
        "id": txn.id,
        "customer_id": txn.customer_id,
        "txn_type": txn.txn_type,
        "amount": txn.amount,
        "bill_id": txn.bill_id,
        "payment_mode": txn.payment_mode,
        "note": txn.note,
        "created_at": txn.created_at,
    }


def get_or_create_customer(name: str, phone: str | None = None) -> dict:
    with get_session() as session:
        customer = session.query(KhataCustomer).filter(KhataCustomer.name == name).first()
        if customer:
            return _customer_to_dict(customer)
        customer = KhataCustomer(name=name, phone=phone)
        session.add(customer)
        session.flush()
        return _customer_to_dict(customer)


def get_customer(name: str) -> dict | None:
    with get_session() as session:
        customer = session.query(KhataCustomer).filter(KhataCustomer.name == name).first()
        return _customer_to_dict(customer) if customer else None


def add_transaction(
    customer_id: int,
    txn_type: str,
    amount: int,
    bill_id: int | None = None,
    payment_mode: str | None = None,
    note: str | None = None,
) -> dict:
    with get_session() as session:
        txn = KhataTransaction(
            customer_id=customer_id,
            txn_type=txn_type,
            amount=amount,
            bill_id=bill_id,
            payment_mode=payment_mode,
            note=note,
        )
        session.add(txn)
        session.flush()
        return _txn_to_dict(txn)


def update_balance(customer_id: int, delta: int) -> dict:
    with get_session() as session:
        customer = (
            session.query(KhataCustomer)
            .filter(KhataCustomer.id == customer_id)
            .with_for_update()
            .one()
        )
        customer.balance += delta
        session.flush()
        return _customer_to_dict(customer)


def get_balance(customer_id: int) -> int:
    with get_session() as session:
        customer = session.query(KhataCustomer).filter(KhataCustomer.id == customer_id).one()
        return customer.balance


def list_customers() -> list[dict]:
    with get_session() as session:
        customers = session.query(KhataCustomer).all()
        return [_customer_to_dict(c) for c in customers]
