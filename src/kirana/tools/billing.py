"""Billing tools — complete billing lifecycle (create → edit → preview → finalize).

This is the most critical skill. Covers 5 of the 9 hard parts:
oversell guard, GST correctness, multi-turn bills, idempotency, concurrency.
"""

from datetime import datetime
from kirana.db.connection import get_session
from kirana.db.models import Bill, BillItem, Product, StockMovement, ChatState, KhataCustomer, KhataTransaction

# ---------------------------------------------------------------------------
# GST math helpers  (all paise integers, no floats for money)
# ---------------------------------------------------------------------------

def _compute_line_tax(quantity: float, sell_price: int, gst_slab: int) -> dict:
    taxable = int(quantity * sell_price)
    tax = (taxable * gst_slab) // 100
    cgst = tax // 2
    sgst = tax - cgst
    line_total = taxable + tax
    return {
        "taxable_amount": taxable,
        "tax": tax,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "line_total": line_total,
    }


def _compute_bill_totals(items: list[dict]) -> dict:
    subtotal = sum(i["taxable_amount"] for i in items)
    total_cgst = sum(i["cgst_amount"] for i in items)
    total_sgst = sum(i["sgst_amount"] for i in items)
    total_tax = total_cgst + total_sgst
    grand_total = subtotal + total_tax
    # Round to nearest rupee
    rounded_rupees = round(grand_total / 100)
    rounded_paise = rounded_rupees * 100
    round_off = rounded_paise - grand_total
    amount_payable = rounded_paise
    return {
        "subtotal": subtotal,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_tax": total_tax,
        "grand_total": grand_total,
        "round_off": round_off,
        "amount_payable": amount_payable,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
        "created_at": bill.created_at.isoformat() if bill.created_at else None,
        "finalized_at": bill.finalized_at.isoformat() if bill.finalized_at else None,
    }


def _item_row_to_dict(item: BillItem) -> dict:
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
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _fmt_price(paise: int) -> str:
    """Format paise to ₹ string."""
    return f"₹{paise // 100}.{paise % 100:02d}"


def _get_items(session, bill_id: int) -> list[BillItem]:
    return session.query(BillItem).filter(BillItem.bill_id == bill_id).all()


def _get_bill_with_items(session, bill_id: int) -> Bill | None:
    return session.query(Bill).filter(Bill.id == bill_id).first()


def _next_bill_number(session) -> str:
    from sqlalchemy import func
    last = session.query(func.max(Bill.bill_number)).scalar()
    if last and last.startswith("INV-"):
        num = int(last.split("-")[1])
        return f"INV-{num + 1:04d}"
    return "INV-0001"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def create_bill(customer_name: str | None = None) -> dict:
    """Start a new draft bill with the next available bill number.

    Args:
        customer_name: Optional customer name for the bill.
    """
    from kirana.agent.context import get_current_chat_id
    from kirana.db.models import ChatState

    chat_id = get_current_chat_id()

    with get_session() as session:
        bill_number = _next_bill_number(session)
        bill = Bill(
            bill_number=bill_number,
            status="draft",
            chat_id=chat_id,
            customer_name=customer_name,
        )
        session.add(bill)
        session.flush()

        if chat_id:
            cs = session.query(ChatState).filter(ChatState.chat_id == chat_id).first()
            if cs:
                cs.active_bill_id = bill.id
            else:
                session.add(ChatState(chat_id=chat_id, active_bill_id=bill.id))

        result = _bill_to_dict(bill)
        result["items"] = []

    return {
        "bill": result,
        "message": f"Created bill {bill_number} (draft).",
    }


def add_item(bill_id: int, product_id: int, quantity: float) -> dict:
    """Add a product line to a draft bill.
    If product already exists in the bill, increments quantity instead.
    Validates bill is draft, product exists, quantity > 0.
    Does NOT decrement stock — stock changes only on finalize.

    Args:
        bill_id: ID of the draft bill
        product_id: ID of the product to add
        quantity: Quantity to add (must be > 0)
    """
    if quantity <= 0:
        return {"error": f"Quantity must be positive, got {quantity}."}

    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return {"error": f"Bill with id {bill_id} not found."}
        if bill.status != "draft":
            return {"error": f"Cannot add items to a {bill.status} bill."}

        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": f"Product with id {product_id} not found."}

        unit_snapshot = f"{product.unit_size}{product.unit_type}" if product.unit_size else product.unit_type

        # Check if product already in bill
        existing = (
            session.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if existing:
            existing.quantity += quantity
            session.flush()
        else:
            item = BillItem(
                bill_id=bill_id,
                product_id=product_id,
                product_name_snapshot=product.name,
                unit_snapshot=unit_snapshot,
                quantity=quantity,
                sell_price=product.sell_price,
                gst_slab=product.gst_slab,
                hsn_code=product.hsn_code,
            )
            session.add(item)
            session.flush()

    # Return full updated bill
    return get_bill(bill_id)


def update_item(bill_id: int, product_id: int, new_quantity: float) -> dict:
    """Change quantity of an existing line in a draft bill.

    Args:
        bill_id: ID of the draft bill
        product_id: ID of the product line to update
        new_quantity: New quantity (must be > 0)
    """
    if new_quantity <= 0:
        return {"error": f"Quantity must be positive, got {new_quantity}."}

    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return {"error": f"Bill with id {bill_id} not found."}
        if bill.status != "draft":
            return {"error": f"Cannot update items in a {bill.status} bill."}

        item = (
            session.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if not item:
            return {"error": f"Product {product_id} not found in bill {bill_id}."}

        item.quantity = new_quantity
        session.flush()

    return get_bill(bill_id)


def remove_item(bill_id: int, product_id: int) -> dict:
    """Remove a product line from a draft bill.

    Args:
        bill_id: ID of the draft bill
        product_id: ID of the product line to remove
    """
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return {"error": f"Bill with id {bill_id} not found."}
        if bill.status != "draft":
            return {"error": f"Cannot remove items from a {bill.status} bill."}

        item = (
            session.query(BillItem)
            .filter(BillItem.bill_id == bill_id, BillItem.product_id == product_id)
            .first()
        )
        if not item:
            return {"error": f"Product {product_id} not found in bill {bill_id}."}

        session.delete(item)
        session.flush()

    return get_bill(bill_id)


def get_bill(bill_id: int) -> dict:
    """Return complete bill state with all items, computed line totals,
    GST breakdown per line, subtotal, CGST/SGST totals, grand total, round-off.

    Args:
        bill_id: ID of the bill
    """
    with get_session() as session:
        bill = _get_bill_with_items(session, bill_id)
        if not bill:
            return {"error": f"Bill with id {bill_id} not found."}

        result = _bill_to_dict(bill)
        rows = _get_items(session, bill_id)

        items = []
        for row in rows:
            item_dict = _item_row_to_dict(row)
            # Compute tax fields (overwrite stored/zero values)
            tax_fields = _compute_line_tax(row.quantity, row.sell_price, row.gst_slab)
            item_dict.update(tax_fields)
            items.append(item_dict)

        result["items"] = items
        totals = _compute_bill_totals(items)
        result.update(totals)

    return {"bill": result}


def cancel_bill(bill_id: int) -> dict:
    """Discard a draft bill. Refuses if already finalized.

    Args:
        bill_id: ID of the bill to cancel
    """
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return {"error": f"Bill with id {bill_id} not found."}
        if bill.status == "finalized":
            return {"error": f"Cannot cancel finalized bill {bill.bill_number}."}
        if bill.status == "cancelled":
            return {"error": f"Bill {bill.bill_number} is already cancelled."}

        bill.status = "cancelled"

        # Clear active bill if this bill was active
        session.query(ChatState).filter(ChatState.active_bill_id == bill_id).update(
            {ChatState.active_bill_id: None}
        )
        session.flush()

    return {
        "bill": {"id": bill_id, "status": "cancelled"},
        "message": f"Bill {bill.bill_number} cancelled.",
    }


def finalize_bill(
    bill_id: int,
    payment_mode: str,
    payment_ref: str | None = None,
    on_credit: bool = False,
    customer_name: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """THE CRITICAL TOOL. Atomically finalizes a bill in a single transaction:
    1. Idempotency check — if already finalized with same key, return existing.
    2. Lock all product rows (SELECT FOR UPDATE).
    3. Oversell check — refuse if any item short.
    4. Decrement stock, record stock_movements.
    5. Compute GST, write totals to bill.
    6. Set status=finalized, payment info, timestamp.
    7. If on_credit, post to khata.
    8. Clear active bill.

    All prices in **paise** (₹1 = 100 paise).

    Args:
        bill_id: ID of the bill to finalize
        payment_mode: Payment method — 'cash', 'upi', 'card', or 'credit'
        payment_ref: Optional payment reference (UTR, transaction ID)
        on_credit: If True, bill goes on customer's credit (khata)
        customer_name: Required if on_credit=True
        idempotency_key: Optional unique key — if bill already finalized with
                         this key, returns same result without re-decrementing
    """
    valid_modes = {"cash", "upi", "card", "credit"}
    if payment_mode not in valid_modes:
        return {"error": f"Invalid payment mode '{payment_mode}'. Must be one of: {', '.join(sorted(valid_modes))}."}

    if on_credit and not customer_name:
        return {"error": "Customer name is required when billing on credit."}

    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return {"error": f"Bill with id {bill_id} not found."}

        # --- Idempotency (hard part #5) ---
        if idempotency_key and bill.status == "finalized" and bill.idempotency_key == idempotency_key:
            # Already finalized with same key — return existing
            rows = _get_items(session, bill_id)
            items = [_item_row_to_dict(r) for r in rows]
            result = _bill_to_dict(bill)
            result["items"] = items
            for item in items:
                tax_fields = _compute_line_tax(item["quantity"], item["sell_price"], item["gst_slab"])
                item.update(tax_fields)
            totals = _compute_bill_totals(items)
            result.update(totals)
            return {"bill": result, "message": f"Bill {bill.bill_number} already finalized (idempotent replay)."}

        if bill.status != "draft":
            return {"error": f"Bill {bill.bill_number} is {bill.status}, cannot finalize."}

        rows = _get_items(session, bill_id)
        if not rows:
            return {"error": f"Bill {bill.bill_number} has no items. Add items before finalizing."}

        # --- Lock product rows and oversell check ---
        product_ids = [r.product_id for r in rows]
        products = (
            session.query(Product)
            .filter(Product.id.in_(product_ids))
            .with_for_update()
            .all()
        )
        product_map = {p.id: p for p in products}
        if len(products) != len(product_ids):
            missing = set(product_ids) - set(p.id for p in products)
            return {"error": f"Products not found: {missing}."}

        oversell_errors = []
        for row in rows:
            prod = product_map[row.product_id]
            if prod.quantity < row.quantity:
                name = row.product_name_snapshot
                oversell_errors.append(
                    f"only {prod.quantity} {name} in stock, bill needs {row.quantity}"
                )

        if oversell_errors:
            return {
                "error": (
                    f"Cannot finalize bill {bill.bill_number}: "
                    + "; ".join(oversell_errors)
                    + ". Remove items or restock first."
                )
            }

        # --- Decrement stock and record movements ---
        for row in rows:
            prod = product_map[row.product_id]
            prod.quantity -= row.quantity
            movement = StockMovement(
                product_id=row.product_id,
                movement_type="out",
                quantity=-row.quantity,
                reference=str(bill_id),
            )
            session.add(movement)

        # --- Compute and write GST totals ---
        items_enhanced = []
        for row in rows:
            tax_fields = _compute_line_tax(row.quantity, row.sell_price, row.gst_slab)
            row.cgst_amount = tax_fields["cgst_amount"]
            row.sgst_amount = tax_fields["sgst_amount"]
            row.line_total = tax_fields["line_total"]
            item_dict = _item_row_to_dict(row)
            item_dict.update(tax_fields)
            items_enhanced.append(item_dict)

        totals = _compute_bill_totals(items_enhanced)
        bill.subtotal = totals["subtotal"]
        bill.total_cgst = totals["total_cgst"]
        bill.total_sgst = totals["total_sgst"]
        bill.total_tax = totals["total_tax"]
        bill.round_off = totals["round_off"]
        bill.grand_total = totals["grand_total"]

        # --- Finalize ---
        bill.status = "finalized"
        bill.payment_mode = payment_mode
        bill.payment_ref = payment_ref
        if idempotency_key:
            bill.idempotency_key = idempotency_key
        bill.finalized_at = datetime.utcnow()

        # --- Credit (khata) ---
        if on_credit:
            customer = session.query(KhataCustomer).filter(KhataCustomer.name == customer_name).first()
            if not customer:
                customer = KhataCustomer(name=customer_name)
                session.add(customer)
                session.flush()
            txn = KhataTransaction(
                customer_id=customer.id,
                txn_type="credit",
                amount=totals["grand_total"],
                bill_id=bill_id,
                payment_mode=payment_mode,
            )
            session.add(txn)
            customer.balance += totals["grand_total"]

        # --- Clear active bill ---
        session.query(ChatState).filter(ChatState.active_bill_id == bill_id).update(
            {ChatState.active_bill_id: None}
        )

        session.flush()

        result = _bill_to_dict(bill)
        result["items"] = items_enhanced
        result.update(totals)

    payment_label = "on credit" if on_credit else f"via {payment_mode}"
    return {
        "bill": result,
        "message": f"Bill {bill.bill_number} finalized ({payment_label}). "
                   f"Total: {_fmt_price(totals['amount_payable'])}.",
    }
