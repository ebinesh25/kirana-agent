from kirana.repo import product_repo, stock_repo, bill_repo, khata_repo, preference_repo


class TestProductRepo:
    def test_create_and_get_product(self):
        p = product_repo.create(
            name="Test Product",
            unit_type="piece",
            cost_price=1000,
            sell_price=1500,
            gst_slab=12,
            hsn_code="1234",
            quantity=10,
        )
        assert p["id"] is not None
        assert p["name"] == "Test Product"
        assert p["cost_price"] == 1000
        assert p["sell_price"] == 1500

        fetched = product_repo.get_by_id(p["id"])
        assert fetched is not None
        assert fetched["name"] == "Test Product"

    def test_search_products_fuzzy(self):
        results = product_repo.search("atta")
        names = [r["name"] for r in results]
        assert "Aashirvaad Atta" in names
        assert "Loose Atta" in names

    def test_search_products_no_match(self):
        results = product_repo.search("xyznonexistent")
        assert results == []

    def test_update_quantity_atomic(self):
        p = product_repo.get_by_id(1)
        old_qty = p["quantity"]
        updated = product_repo.update_quantity(1, 5.0)
        assert updated["quantity"] == old_qty + 5.0

    def test_low_stock_filter(self):
        low = product_repo.get_low_stock()
        for p in low:
            assert p["quantity"] <= p["reorder_level"]


class TestStockRepo:
    def test_stock_movement_audit_trail(self):
        m = stock_repo.record_movement(
            product_id=1,
            movement_type="in",
            quantity=10.0,
            reference="test",
        )
        assert m["id"] is not None
        assert m["movement_type"] == "in"

        movements = stock_repo.get_movements(product_id=1)
        assert len(movements) >= 1


class TestBillRepo:
    def test_create_bill_and_add_items(self):
        bill = bill_repo.create_bill(chat_id="test_chat")
        assert bill["id"] is not None
        assert bill["status"] == "draft"

        item = bill_repo.add_item(
            bill_id=bill["id"],
            product_id=1,
            product_name_snapshot="Test Product",
            unit_snapshot="piece",
            quantity=2,
            sell_price=1000,
            gst_slab=12,
            hsn_code="1234",
        )
        assert item["id"] is not None

        fetched = bill_repo.get_bill(bill["id"])
        assert len(fetched["items"]) == 1

    def test_update_and_remove_bill_items(self):
        bill = bill_repo.create_bill(chat_id="test_chat2")
        bill_repo.add_item(
            bill_id=bill["id"],
            product_id=1,
            product_name_snapshot="Test",
            unit_snapshot="piece",
            quantity=2,
            sell_price=1000,
            gst_slab=12,
            hsn_code="1234",
        )
        updated = bill_repo.update_item(bill["id"], product_id=1, new_qty=5)
        assert updated["quantity"] == 5

        removed = bill_repo.remove_item(bill["id"], product_id=1)
        assert removed is not None
        items = bill_repo.get_items(bill["id"])
        assert len(items) == 0

    def test_next_bill_number_increments(self):
        n1 = bill_repo.next_bill_number()
        bill_repo.create_bill(chat_id="test_num")
        n2 = bill_repo.next_bill_number()
        assert n2 != n1


class TestKhataRepo:
    def test_get_or_create_customer(self):
        c = khata_repo.get_or_create_customer("Ramesh", phone="9999999999")
        assert c["name"] == "Ramesh"
        assert c["phone"] == "9999999999"

        c2 = khata_repo.get_or_create_customer("Ramesh")
        assert c2["id"] == c["id"]

    def test_khata_balance_updates(self):
        c = khata_repo.get_or_create_customer("Suresh")
        updated = khata_repo.update_balance(c["id"], 50000)
        assert updated["balance"] == 50000

        bal = khata_repo.get_balance(c["id"])
        assert bal == 50000


class TestPreferenceRepo:
    def test_preference_upsert(self):
        pref = preference_repo.set("shop_name", "My Kirana")
        assert pref["value"] == "My Kirana"

        pref2 = preference_repo.set("shop_name", "Updated Kirana")
        assert pref2["value"] == "Updated Kirana"

    def test_preference_get_all(self):
        preference_repo.set("key1", "val1")
        preference_repo.set("key2", "val2")
        all_prefs = preference_repo.get_all()
        assert all_prefs["key1"] == "val1"
        assert all_prefs["key2"] == "val2"
