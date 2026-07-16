"""Tests for billing tool functions.

Tests call tools directly (not through the agent loop).
Uses test DB fixtures: create_all + seed per test.
"""

import pytest
from kirana.db.connection import engine
from kirana.tools.billing import (
    create_bill, add_item, update_item, remove_item,
    get_bill, finalize_bill, cancel_bill,
)
from kirana.repo import product_repo, stock_repo


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------

class TestBillLifecycle:
    def test_create_bill_returns_draft(self):
        result = create_bill()
        assert "bill" in result
        b = result["bill"]
        assert b["status"] == "draft"
        assert b["bill_number"].startswith("INV-")
        assert b["items"] == []

    def test_add_item_to_draft(self):
        b = create_bill()["bill"]
        result = add_item(b["id"], product_id=5, quantity=2)
        assert "bill" in result
        items = result["bill"]["items"]
        assert len(items) == 1
        assert items[0]["product_name_snapshot"] == "Maggi Noodles"
        assert items[0]["quantity"] == 2.0

    def test_add_item_increments_existing_line(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)
        result = add_item(b["id"], product_id=5, quantity=3)
        items = result["bill"]["items"]
        assert len(items) == 1
        assert items[0]["quantity"] == 5.0

    def test_add_item_rejects_finalized_bill(self):
        b = create_bill()["bill"]
        maggi = product_repo.get_by_id(5)
        # adjust stock so there's enough for finalize
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        result = add_item(b["id"], product_id=5, quantity=1)
        assert "error" in result
        assert "finalized" in result["error"].lower()

    def test_add_item_rejects_nonexistent_product(self):
        b = create_bill()["bill"]
        result = add_item(b["id"], product_id=9999, quantity=1)
        assert "error" in result

    def test_update_item_quantity(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)
        result = update_item(b["id"], product_id=5, new_quantity=6)
        items = result["bill"]["items"]
        assert items[0]["quantity"] == 6.0

    def test_remove_item_from_draft(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)
        add_item(b["id"], product_id=3, quantity=1)
        result = remove_item(b["id"], product_id=5)
        items = result["bill"]["items"]
        assert len(items) == 1
        assert items[0]["product_id"] == 3

    def test_get_bill_shows_running_totals(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi, ₹14, 12% GST
        add_item(b["id"], product_id=2, quantity=1)  # Tata Salt, ₹28, 0% GST
        result = get_bill(b["id"])
        bill = result["bill"]
        assert bill["subtotal"] > 0
        assert bill["total_tax"] > 0
        assert len(bill["items"]) == 2

    def test_get_bill_shows_gst_breakup_per_line(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi, 12% GST
        result = get_bill(b["id"])
        item = result["bill"]["items"][0]
        assert item["cgst_amount"] is not None
        assert item["sgst_amount"] is not None
        assert item["taxable_amount"] is not None
        assert item["line_total"] is not None

    def test_cancel_draft_bill(self):
        b = create_bill()["bill"]
        result = cancel_bill(b["id"])
        assert result["bill"]["status"] == "cancelled"

    def test_cancel_finalized_bill_rejected(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        result = cancel_bill(b["id"])
        assert "error" in result


# ---------------------------------------------------------------------------
# Finalize — happy path
# ---------------------------------------------------------------------------

class TestFinalizeHappyPath:
    def test_finalize_bill_decrements_stock(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=10)  # Maggi: 48 → 38
        finalize_bill(b["id"], payment_mode="cash")
        prod = product_repo.get_by_id(5)
        assert prod["quantity"] == 38.0

    def test_finalize_bill_computes_gst_correctly(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi: 2 × ₹14 = 2800 paise, 12% GST
        result = finalize_bill(b["id"], payment_mode="cash")
        bill = result["bill"]
        # taxable = int(2 * 1400) = 2800
        # tax = 2800 * 12 // 100 = 336
        # cgst = 168, sgst = 168, line_total = 3136
        assert bill["subtotal"] == 2800
        assert bill["total_cgst"] == 168
        assert bill["total_sgst"] == 168
        assert bill["total_tax"] == 336
        assert bill["grand_total"] == 3136

    def test_finalize_bill_sets_status_finalized(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        result = finalize_bill(b["id"], payment_mode="cash")
        assert result["bill"]["status"] == "finalized"
        assert result["bill"]["finalized_at"] is not None

    def test_finalize_bill_records_stock_movements(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=10)
        finalize_bill(b["id"], payment_mode="cash")
        movements = stock_repo.get_movements(product_id=5)
        out_moves = [m for m in movements if m["movement_type"] == "out"]
        assert len(out_moves) >= 1
        assert out_moves[0]["quantity"] == -10.0

    def test_finalize_bill_cash_payment(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        result = finalize_bill(b["id"], payment_mode="cash")
        assert result["bill"]["payment_mode"] == "cash"

    def test_finalize_bill_upi_payment(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        result = finalize_bill(b["id"], payment_mode="upi", payment_ref="UTR123")
        assert result["bill"]["payment_mode"] == "upi"
        assert result["bill"]["payment_ref"] == "UTR123"

    def test_finalize_bill_credit_posts_to_khata(self):
        from kirana.repo import khata_repo
        b = create_bill(customer_name="Ramesh")["bill"]
        add_item(b["id"], product_id=5, quantity=2)
        result = finalize_bill(b["id"], payment_mode="cash", on_credit=True, customer_name="Ramesh")
        assert result["bill"]["status"] == "finalized"
        # Check khata
        customer = khata_repo.get_or_create_customer("Ramesh")
        assert customer["balance"] == result["bill"]["grand_total"]


# ---------------------------------------------------------------------------
# Oversell guard (hard part #2)
# ---------------------------------------------------------------------------

class TestOversellGuard:
    def test_oversell_refused_at_finalize(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=999)  # Maggi only has 48
        result = finalize_bill(b["id"], payment_mode="cash")
        assert "error" in result

    def test_oversell_does_not_decrement_any_stock(self):
        """One item short → NO items decremented."""
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=999)  # Maggi: oversell
        add_item(b["id"], product_id=2, quantity=1)    # Tata Salt: fine
        finalize_bill(b["id"], payment_mode="cash")
        prod5 = product_repo.get_by_id(5)
        prod2 = product_repo.get_by_id(2)
        assert prod5["quantity"] == 48  # unchanged
        assert prod2["quantity"] == 30  # unchanged

    def test_oversell_error_names_product_and_qty(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=999)
        add_item(b["id"], product_id=2, quantity=1)
        result = finalize_bill(b["id"], payment_mode="cash")
        assert "error" in result
        assert "Maggi" in result["error"]
        assert "999" in result["error"]


# ---------------------------------------------------------------------------
# GST correctness (hard part #3)
# ---------------------------------------------------------------------------

class TestGSTCorrectness:
    def test_gst_0_percent_item(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=2, quantity=1)  # Tata Salt, GST 0%
        result = finalize_bill(b["id"], payment_mode="cash")
        item = result["bill"]["items"][0]
        assert item["cgst_amount"] == 0
        assert item["sgst_amount"] == 0
        assert item["tax"] == 0

    def test_gst_5_percent_item(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=1, quantity=2)  # Aashirvaad Atta, ₹260, GST 5%
        result = finalize_bill(b["id"], payment_mode="cash")
        item = result["bill"]["items"][0]
        # taxable = int(2 * 26000) = 52000
        # tax = 52000 * 5 // 100 = 2600
        # cgst = 1300, sgst = 1300
        assert item["cgst_amount"] == 1300
        assert item["sgst_amount"] == 1300
        assert item["tax"] == 2600

    def test_gst_12_percent_item(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi, ₹14, GST 12%
        result = finalize_bill(b["id"], payment_mode="cash")
        item = result["bill"]["items"][0]
        assert item["cgst_amount"] == 168
        assert item["sgst_amount"] == 168
        assert item["tax"] == 336

    def test_gst_18_percent_item(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=7, quantity=1)  # Surf Excel, ₹120, GST 18%
        result = finalize_bill(b["id"], payment_mode="cash")
        item = result["bill"]["items"][0]
        # taxable = 12000
        # tax = 12000 * 18 // 100 = 2160
        # cgst = 1080, sgst = 1080
        assert item["cgst_amount"] == 1080
        assert item["sgst_amount"] == 1080
        assert item["line_total"] == 14160

    def test_gst_cgst_sgst_odd_paisa(self):
        """When tax is odd, cgst gets floor, sgst gets ceil."""
        b = create_bill()["bill"]
        # Need a line where tax is odd
        # sell_price=100, qty=1, gst=5 → tax = 100*5//100 = 5 → cgst=2, sgst=3
        # First add a test product manually or find one with right values
        from kirana.db.connection import get_session
        from kirana.db.models import Product
        with get_session() as s:
            existing = s.query(Product).filter(Product.gst_slab == 5).first()
            # Use existing product with GST 5% where taxable * 5% gives odd tax
            pass
        # Force by using Aashirvaad Atta with qty 1: taxable=26000, tax=1300, cgst=650, sgst=650 (even)
        # Use a smaller taxable: we know sell_price=1400 for Maggi, qty=1, gst=12
        # taxable=1400, tax=168 → even
        # Let's compute: we need (qty*sell_price)*gst/100 to be odd
        # For GST 5%: taxable * 5 // 100 = odd → taxable must be odd*20
        # e.g. taxable=100 → tax=5 → cgst=2, sgst=3 ✓
        # For GST 12%: taxable * 12 // 100 = odd → taxable must be odd*25/3
        # That's harder. Let me use GST 5% with taxable=100.
        # But no seed product has that exact combination.
        # Test the function's internal behavior directly:
        from kirana.tools.billing import _compute_line_tax
        result = _compute_line_tax(1, 100, 5)
        assert result["tax"] == 5
        assert result["cgst_amount"] == 2
        assert result["sgst_amount"] == 3

    def test_gst_rounding(self):
        """Verify rounding to nearest rupee."""
        b = create_bill()["bill"]
        # Add items to get grand_total that needs rounding
        add_item(b["id"], product_id=5, quantity=1)  # Maggi: taxable=1400, tax=168, line=1568
        add_item(b["id"], product_id=2, quantity=1)  # Salt: taxable=2800, tax=0, line=2800
        # subtotal=4200, tax=168, grand_total=4368
        # round(4368/100)=44, 44*100=4400, round_off=4400-4368=32
        result = finalize_bill(b["id"], payment_mode="cash")
        bill = result["bill"]
        assert bill["round_off"] == 32  # 4400 - 4368
        assert bill["amount_payable"] == 4400


# ---------------------------------------------------------------------------
# Multi-turn bills (hard part #4)
# ---------------------------------------------------------------------------

class TestMultiTurnBills:
    def test_draft_persists_across_calls(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)
        add_item(b["id"], product_id=3, quantity=1)
        # Second get_bill call
        result = get_bill(b["id"])
        assert len(result["bill"]["items"]) == 2

    def test_stock_unchanged_during_draft(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=999)
        prod = product_repo.get_by_id(5)
        assert prod["quantity"] == 48  # unchanged despite large qty added

    def test_edit_then_finalize(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=3)
        update_item(b["id"], product_id=5, new_quantity=5)
        result = finalize_bill(b["id"], payment_mode="cash")
        assert result["bill"]["status"] == "finalized"
        prod = product_repo.get_by_id(5)
        assert prod["quantity"] == 43  # 48 - 5


# ---------------------------------------------------------------------------
# Idempotency (hard part #5)
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_finalize_idempotent_same_key(self):
        """Finalize twice with same key → same result, stock decremented once."""
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=10)
        r1 = finalize_bill(b["id"], payment_mode="cash", idempotency_key="key1")
        assert r1["bill"]["status"] == "finalized"
        prod_after_first = product_repo.get_by_id(5)
        assert prod_after_first["quantity"] == 38

        r2 = finalize_bill(b["id"], payment_mode="cash", idempotency_key="key1")
        assert r2["bill"]["status"] == "finalized"
        # Stock should NOT have been decremented again
        prod_after_second = product_repo.get_by_id(5)
        assert prod_after_second["quantity"] == 38

    def test_finalize_already_finalized_no_key(self):
        """Finalize twice without key → error."""
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        result = finalize_bill(b["id"], payment_mode="cash")
        assert "error" in result


# ---------------------------------------------------------------------------
# Concurrency (hard part #6)
# ---------------------------------------------------------------------------

def _is_sqlite():
    return engine.url.get_backend_name() == "sqlite"


class TestConcurrency:
    @pytest.mark.xfail(_is_sqlite(), reason="SQLite lacks row-level locking; requires Postgres")
    def test_concurrent_finalize_oversell(self):
        """Two threads, same product, total > stock → one succeeds, one fails."""
        from concurrent.futures import ThreadPoolExecutor, wait

        b = create_bill()["bill"]
        bid = b["id"]

        # Create two bills, each wanting 30 Maggi (only 48 in stock, so only 1 can succeed)
        b1 = create_bill()["bill"]
        add_item(b1["id"], product_id=5, quantity=30)

        b2 = create_bill()["bill"]
        add_item(b2["id"], product_id=5, quantity=30)

        results = []

        def finalize_bid(bill_id):
            r = finalize_bill(bill_id, payment_mode="cash")
            results.append(r)
            return r

        executor = ThreadPoolExecutor(max_workers=2)
        fut1 = executor.submit(finalize_bid, b1["id"])
        fut2 = executor.submit(finalize_bid, b2["id"])
        wait([fut1, fut2])
        executor.shutdown()

        successes = [r for r in results if "bill" in r and r["bill"]["status"] == "finalized"]
        errors = [r for r in results if "error" in r]

        assert len(successes) == 1
        assert len(errors) == 1

        # Stock should never be negative
        prod = product_repo.get_by_id(5)
        assert prod["quantity"] >= 0
        # Stock decremented exactly once by 30
        assert prod["quantity"] == 48 - 30

    def test_concurrent_finalize_different_products(self):
        """Two threads, different products → both succeed."""
        from concurrent.futures import ThreadPoolExecutor, wait

        b1 = create_bill()["bill"]
        add_item(b1["id"], product_id=5, quantity=10)  # Maggi
        b2 = create_bill()["bill"]
        add_item(b2["id"], product_id=3, quantity=5)   # Butter

        results = []

        def finalize_bid(bill_id):
            r = finalize_bill(bill_id, payment_mode="cash")
            results.append(r)
            return r

        executor = ThreadPoolExecutor(max_workers=2)
        fut1 = executor.submit(finalize_bid, b1["id"])
        fut2 = executor.submit(finalize_bid, b2["id"])
        wait([fut1, fut2])
        executor.shutdown()

        assert all(r["bill"]["status"] == "finalized" for r in results)
        assert product_repo.get_by_id(5)["quantity"] == 38  # 48 - 10
        assert product_repo.get_by_id(3)["quantity"] == 10  # 15 - 5


# ---------------------------------------------------------------------------
# Guardrails (hard part #7)
# ---------------------------------------------------------------------------

class TestBillingGuardrails:
    def test_finalize_rejects_unknown_payment_mode(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        result = finalize_bill(b["id"], payment_mode="bitcoin")
        assert "error" in result

    def test_credit_without_customer_name_rejected(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        result = finalize_bill(b["id"], payment_mode="cash", on_credit=True)
        assert "error" in result
        assert "customer name" in result["error"].lower()

    def test_finalize_empty_bill_rejected(self):
        b = create_bill()["bill"]
        result = finalize_bill(b["id"], payment_mode="cash")
        assert "error" in result
        assert "no items" in result["error"].lower()
