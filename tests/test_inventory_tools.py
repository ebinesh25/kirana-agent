"""Tests for inventory tool functions.

Tests call tools directly (not through the agent loop).
Uses test DB fixtures from conftest.py (create_all + seed per test).
"""

from kirana.tools.inventory import (
    search_products,
    add_product,
    receive_stock,
    get_stock,
    get_low_stock,
    adjust_stock,
)
from kirana.repo import product_repo


# ---------------------------------------------------------------------------
# search_products
# ---------------------------------------------------------------------------

class TestSearchProducts:
    def test_search_exact_match(self):
        result = search_products("Maggi")
        assert result["count"] >= 1
        names = [p["name"] for p in result["products"]]
        assert "Maggi Noodles" in names

    def test_search_partial_match(self):
        result = search_products("att")
        names = [p["name"] for p in result["products"]]
        assert "Aashirvaad Atta" in names
        assert "Loose Atta" in names

    def test_search_no_results(self):
        result = search_products("xyznonexistent")
        assert result["count"] == 0
        assert result["products"] == []


# ---------------------------------------------------------------------------
# add_product
# ---------------------------------------------------------------------------

class TestAddProduct:
    def test_add_product_success(self):
        result = add_product(
            name="Test Detergent",
            brand="Test Brand",
            unit_size=500,
            unit_type="g",
            cost_price=8000,
            sell_price=10000,
            mrp=10000,
            gst_slab=18,
            hsn_code="3402",
            reorder_level=5,
        )
        assert "product" in result
        assert result["product"]["name"] == "Test Detergent"
        assert result["product"]["cost_price"] == 8000
        assert result["product"]["sell_price"] == 10000
        assert result["product"]["quantity"] == 0.0  # starts at 0

        # Verify it persisted
        fetched = product_repo.get_by_id(result["product"]["id"])
        assert fetched["name"] == "Test Detergent"

    def test_add_product_rejects_bad_gst(self):
        result = add_product(
            name="Bad GST",
            unit_type="piece",
            cost_price=100,
            sell_price=200,
            gst_slab=7,
            hsn_code="1234",
        )
        assert "error" in result
        assert "7" in result["error"]

    def test_add_product_rejects_sell_below_cost(self):
        result = add_product(
            name="Below Cost",
            unit_type="piece",
            cost_price=1000,
            sell_price=500,
            gst_slab=5,
            hsn_code="1234",
        )
        assert "error" in result
        assert "below" in result["error"].lower()

    def test_add_product_rejects_missing_hsn(self):
        result = add_product(
            name="No HSN",
            unit_type="piece",
            cost_price=100,
            sell_price=200,
            gst_slab=5,
            hsn_code="",
        )
        assert "error" in result
        assert "HSN" in result["error"]

    def test_add_product_rejects_duplicate(self):
        # First add works
        r1 = add_product(
            name="Unique Product",
            unit_type="piece",
            cost_price=1000,
            sell_price=1500,
            gst_slab=12,
            hsn_code="1234",
        )
        assert "product" in r1

        # Second add with same name+unit should fail
        r2 = add_product(
            name="Unique Product",
            unit_type="piece",
            cost_price=1000,
            sell_price=1500,
            gst_slab=12,
            hsn_code="1234",
        )
        assert "error" in r2


# ---------------------------------------------------------------------------
# receive_stock
# ---------------------------------------------------------------------------

class TestReceiveStock:
    def test_receive_stock_increments_qty(self):
        # Maggi Noodles is product_id 5, qty 48
        result = receive_stock(product_id=5, quantity=50)
        assert "product" in result
        assert result["product"]["quantity"] == 98.0  # 48 + 50

    def test_receive_stock_records_movement(self):
        from kirana.repo import stock_repo
        receive_stock(product_id=5, quantity=20)
        movements = stock_repo.get_movements(product_id=5)
        types = [m["movement_type"] for m in movements]
        assert "in" in types
        # Find the latest "in" movement
        in_moves = [m for m in movements if m["movement_type"] == "in"]
        assert in_moves[0]["quantity"] == 20

    def test_receive_stock_updates_cost_price(self):
        result = receive_stock(product_id=5, quantity=10, cost_price=1300)
        assert result["product"]["cost_price"] == 1300

    def test_receive_stock_rejects_negative_qty(self):
        result = receive_stock(product_id=5, quantity=-5)
        assert "error" in result

    def test_receive_stock_rejects_bad_product_id(self):
        result = receive_stock(product_id=9999, quantity=10)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_stock
# ---------------------------------------------------------------------------

class TestGetStock:
    def test_get_stock_returns_correct_data(self):
        result = get_stock(product_id=1)
        assert "product" in result
        p = result["product"]
        assert p["name"] == "Aashirvaad Atta"
        assert p["cost_price"] == 22000
        assert p["sell_price"] == 26000

    def test_get_stock_nonexistent_returns_error(self):
        result = get_stock(product_id=9999)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_low_stock
# ---------------------------------------------------------------------------

class TestLowStock:
    def test_low_stock_returns_only_low_items(self):
        # First make Maggi (id=5) low by adjusting stock
        adjust_stock(product_id=5, new_quantity=2, reason="test low stock")
        result = get_low_stock()
        assert result["count"] >= 1
        product_ids = [p["id"] for p in result["products"]]
        assert 5 in product_ids
        for p in result["products"]:
            assert p["quantity"] <= p["reorder_level"]


# ---------------------------------------------------------------------------
# adjust_stock
# ---------------------------------------------------------------------------

class TestAdjustStock:
    def test_adjust_stock_with_reason(self):
        # Maggi is id=5, qty=48
        result = adjust_stock(product_id=5, new_quantity=40, reason="damaged 8 packets")
        assert "product" in result
        assert result["product"]["quantity"] == 40.0

    def test_adjust_stock_rejects_negative(self):
        result = adjust_stock(product_id=5, new_quantity=-5, reason="test")
        assert "error" in result

    def test_adjust_stock_requires_reason(self):
        result = adjust_stock(product_id=5, new_quantity=30, reason="")
        assert "error" in result

    def test_adjust_stock_rejects_bad_product_id(self):
        result = adjust_stock(product_id=9999, new_quantity=10, reason="test")
        assert "error" in result
