"""Tests for analytics/daily-close tool functions.

Tests call tools directly. Uses test DB fixtures from conftest.py.
"""

import pytest
from datetime import datetime, timedelta
from kirana.tools.analytics import (
    get_daily_summary,
    get_sales_analysis,
    get_inventory_value,
)
from kirana.tools.billing import create_bill, add_item, finalize_bill
from kirana.tools.inventory import receive_stock
from kirana.db.connection import get_session
from kirana.db.models import Bill


def _force_finalized_at(bill_id: int, dt: datetime):
    """Override finalized_at for testing (bypasses auto-set in finalize_bill)."""
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if bill:
            bill.finalized_at = dt


# ---------------------------------------------------------------------------
# get_daily_summary
# ---------------------------------------------------------------------------

class TestGetDailySummary:
    def test_summary_no_bills(self):
        result = get_daily_summary("2024-01-01")
        assert result["bill_count"] == 0
        assert result["total_sales"] == 0

    def test_summary_with_bills(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi: 2×1400=2800, GST 12%
        finalize_bill(b["id"], payment_mode="cash")
        # Get today's summary
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        result = get_daily_summary(today_str)
        assert result["bill_count"] >= 1
        assert result["total_sales"] >= 2800

    def test_summary_payment_breakdown(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        result = get_daily_summary(today_str)
        assert "cash" in result["payment_breakdown"]

    def test_summary_gst_by_slab(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi: 12%
        finalize_bill(b["id"], payment_mode="cash")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        result = get_daily_summary(today_str)
        slabs = [s["gst_slab"] for s in result["gst_by_slab"]]
        assert 12 in slabs

    def test_summary_top_items(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=3)
        finalize_bill(b["id"], payment_mode="cash")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        result = get_daily_summary(today_str)
        assert len(result["top_items"]) >= 1
        assert result["top_items"][0]["product"] == "Maggi Noodles"

    def test_summary_bad_date(self):
        result = get_daily_summary("not-a-date")
        assert "error" in result


# ---------------------------------------------------------------------------
# get_sales_analysis
# ---------------------------------------------------------------------------

class TestGetSalesAnalysis:
    def test_analysis_empty_range(self):
        result = get_sales_analysis("2020-01-01", "2020-01-02")
        assert result["period_summary"]["bill_count"] == 0

    def test_analysis_with_data(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = get_sales_analysis(yesterday, today_str)
        assert result["period_summary"]["total_sales"] > 0
        assert len(result["daily_trend"]) >= 1

    def test_analysis_bad_date(self):
        result = get_sales_analysis("bad", "date")
        assert "error" in result

    def test_analysis_start_after_end(self):
        result = get_sales_analysis("2024-12-31", "2024-01-01")
        assert "error" in result

    def test_analysis_payment_distribution(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = get_sales_analysis(yesterday, today_str)
        assert "cash" in result["payment_distribution"]

    def test_analysis_gst_by_slab(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=2, quantity=1)  # Tata Salt: 0% GST
        finalize_bill(b["id"], payment_mode="cash")
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = get_sales_analysis(yesterday, today_str)
        slabs = [s["gst_slab"] for s in result["gst_by_slab"]]
        assert 0 in slabs


# ---------------------------------------------------------------------------
# get_inventory_value
# ---------------------------------------------------------------------------

class TestGetInventoryValue:
    def test_inventory_value_returns_counts(self):
        result = get_inventory_value()
        assert result["product_count"] >= 12  # seed has 12 products
        assert result["total_cost_value"] > 0
        assert result["total_retail_value"] > 0

    def test_inventory_value_increases_after_receive(self):
        before = get_inventory_value()
        receive_stock(product_id=5, quantity=10, cost_price=1200)
        after = get_inventory_value()
        # Maggi cost 1200 × 10 = 12000 more cost, sell 1400 × 10 = 14000 more retail
        assert after["total_cost_value"] > before["total_cost_value"]
        assert after["total_retail_value"] > before["total_retail_value"]

    def test_inventory_value_items_sorted(self):
        result = get_inventory_value()
        if result["items"]:
            values = [i["retail_value"] for i in result["items"]]
            assert values == sorted(values, reverse=True)
