"""Khata (credit ledger) tools for Phase 4.

Customers get credit (on-credit sale) and settle (repayment).
All amounts in paise.
"""

from sqlalchemy import func
from kirana.db.connection import get_session
from kirana.db.models import Bill, KhataCustomer, KhataTransaction
from kirana.repo import khata_repo


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fmt_price(paise: int) -> str:
    return f"\u20b9{paise // 100}.{paise % 100:02d}"


def _customer_to_dict(c: KhataCustomer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "balance": c.balance,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _txn_to_dict(t: KhataTransaction) -> dict:
    return {
        "id": t.id,
        "customer_id": t.customer_id,
        "txn_type": t.txn_type,
        "amount": t.amount,
        "bill_id": t.bill_id,
        "payment_mode": t.payment_mode,
        "note": t.note,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def get_or_create_customer(name: str, phone: str | None = None) -> dict:
    """Find customer by name (case-insensitive) or create new one.

    Args:
        name: Customer name (case-insensitive match)
        phone: Optional phone number for new customers
    """
    with get_session() as session:
        customer = (
            session.query(KhataCustomer)
            .filter(func.lower(KhataCustomer.name) == func.lower(name))
            .first()
        )
        if customer:
            return {"customer": _customer_to_dict(customer)}

        customer = KhataCustomer(name=name, phone=phone)
        session.add(customer)
        session.flush()

        return {
            "customer": _customer_to_dict(customer),
            "message": f"Created new customer '{name}'.",
        }


def add_credit(
    customer_name: str,
    amount: int,
    bill_id: int | None = None,
    note: str | None = None,
) -> dict:
    """Record a credit (sale-on-credit) for a customer.

    Atomically inserts a transaction and updates the customer balance.

    Args:
        customer_name: Name of the customer
        amount: Amount in paise being credited (positive integer)
        bill_id: Optional bill ID this credit is linked to
        note: Optional note
    """
    if amount <= 0:
        return {"error": f"Amount must be positive, got {_fmt_price(amount)}."}

    with get_session() as session:
        customer = (
            session.query(KhataCustomer)
            .filter(func.lower(KhataCustomer.name) == func.lower(customer_name))
            .with_for_update()
            .first()
        )
        if not customer:
            return {"error": f"Customer '{customer_name}' not found. Create them first with get_or_create_customer."}

        txn = KhataTransaction(
            customer_id=customer.id,
            txn_type="credit",
            amount=amount,
            bill_id=bill_id,
            note=note,
        )
        session.add(txn)
        customer.balance += amount
        session.flush()

        customer_dict = _customer_to_dict(customer)
        txn_dict = _txn_to_dict(txn)

    return {
        "customer": customer_dict,
        "transaction": txn_dict,
        "message": (
            f"Added credit of {_fmt_price(amount)} to {customer_name}. "
            f"New balance: {_fmt_price(customer_dict['balance'])}."
        ),
    }


def settle_credit(
    customer_name: str,
    amount: int,
    payment_mode: str | None = None,
    note: str | None = None,
) -> dict:
    """Record a settlement (repayment) against a customer's credit.

    Atomically inserts a settle transaction and decreases balance.
    Refuses if amount exceeds current balance — agent must ask user.

    Args:
        customer_name: Name of the customer
        amount: Amount in paise being settled (positive integer)
        payment_mode: Optional payment mode (cash/upi/card)
        note: Optional note
    """
    if amount <= 0:
        return {"error": f"Amount must be positive, got {_fmt_price(amount)}."}

    with get_session() as session:
        customer = (
            session.query(KhataCustomer)
            .filter(func.lower(KhataCustomer.name) == func.lower(customer_name))
            .with_for_update()
            .first()
        )
        if not customer:
            return {"error": f"Customer '{customer_name}' not found."}

        if amount > customer.balance:
            return {
                "error": (
                    f"Settlement of {_fmt_price(amount)} exceeds balance "
                    f"of {_fmt_price(customer.balance)} for {customer_name}. "
                    "Ask user if they want to settle the full balance instead."
                )
            }

        txn = KhataTransaction(
            customer_id=customer.id,
            txn_type="settle",
            amount=amount,
            payment_mode=payment_mode,
            note=note,
        )
        session.add(txn)
        customer.balance -= amount
        session.flush()

        customer_dict = _customer_to_dict(customer)
        txn_dict = _txn_to_dict(txn)

    return {
        "customer": customer_dict,
        "transaction": txn_dict,
        "message": (
            f"Settled {_fmt_price(amount)} from {customer_name}. "
            f"Remaining balance: {_fmt_price(customer_dict['balance'])}."
        ),
    }


def get_balance(customer_name: str) -> dict:
    """Get current khata balance for a customer.

    Args:
        customer_name: Name of the customer (case-insensitive)
    """
    customer = khata_repo.get_customer(customer_name)
    if not customer:
        return {"error": f"Customer '{customer_name}' not found."}

    return {
        "customer": customer,
        "message": (
            f"{customer['name']}: balance {_fmt_price(customer['balance'])}."
        ),
    }


def list_khata() -> dict:
    """List all khata customers sorted by balance descending."""
    customers = khata_repo.list_customers()
    customers.sort(key=lambda c: c["balance"], reverse=True)

    if not customers:
        return {"customers": [], "count": 0, "message": "No khata customers yet."}

    lines = []
    for c in customers:
        direction = "owes" if c["balance"] > 0 else ("is owed" if c["balance"] < 0 else "settled")
        lines.append(f"{c['name']}: {_fmt_price(c['balance'])} ({direction})")

    return {
        "customers": customers,
        "count": len(customers),
        "message": f"{len(customers)} customer(s):\n" + "\n".join(lines),
    }


def get_top_customers(n: int = 10) -> dict:
    """List top customers by total spend across finalized bills.

    Args:
        n: Number of top customers to return (default 10, max 50)
    """
    n = min(max(n, 1), 50)

    with get_session() as session:
        rows = (
            session.query(
                Bill.customer_name,
                func.sum(Bill.grand_total).label("total_spent"),
                func.count(Bill.id).label("bill_count"),
            )
            .filter(
                Bill.status == "finalized",
                Bill.customer_name.isnot(None),
            )
            .group_by(Bill.customer_name)
            .order_by(func.sum(Bill.grand_total).desc())
            .limit(n)
            .all()
        )

        if not rows:
            return {"customers": [], "message": "No customer spend data yet."}

        customers = [
            {
                "name": r.customer_name,
                "total_spent": int(r.total_spent),
                "total_spent_fmt": _fmt_price(int(r.total_spent)),
                "bill_count": r.bill_count,
            }
            for r in rows
        ]

        lines = [
            f"{i+1}. {c['name']} — {c['total_spent_fmt']} ({c['bill_count']} bills)"
            for i, c in enumerate(customers)
        ]

        return {
            "customers": customers,
            "count": len(customers),
            "message": f"Top {len(customers)} customer(s) by spend:\n" + "\n".join(lines),
        }
