"""Tests for khata (credit ledger) tool functions.

Tests call tools directly. Uses test DB fixtures from conftest.py.
"""

from kirana.tools.khata import (
    get_or_create_customer,
    add_credit,
    settle_credit,
    get_balance,
    list_khata,
)


# ---------------------------------------------------------------------------
# get_or_create_customer
# ---------------------------------------------------------------------------

class TestGetOrCreateCustomer:
    def test_creates_new_customer(self):
        result = get_or_create_customer("Ramesh")
        assert "customer" in result
        assert result["customer"]["name"] == "Ramesh"
        assert result["customer"]["balance"] == 0

    def test_get_existing_customer(self):
        r1 = get_or_create_customer("Suresh")
        r2 = get_or_create_customer("Suresh")
        assert r2["customer"]["id"] == r1["customer"]["id"]

    def test_case_insensitive_lookup(self):
        r1 = get_or_create_customer("Mahesh")
        r2 = get_or_create_customer("mahesh")
        assert r2["customer"]["id"] == r1["customer"]["id"]

    def test_phone_on_create(self):
        result = get_or_create_customer("PhoneTest", phone="9876543210")
        assert result["customer"]["phone"] == "9876543210"


# ---------------------------------------------------------------------------
# add_credit
# ---------------------------------------------------------------------------

class TestAddCredit:
    def test_add_credit_increases_balance(self):
        get_or_create_customer("CreditTest")
        result = add_credit("CreditTest", amount=50000)
        assert result["customer"]["balance"] == 50000
        assert result["transaction"]["txn_type"] == "credit"

    def test_add_credit_multiple_times(self):
        get_or_create_customer("MultiCredit")
        add_credit("MultiCredit", amount=20000)
        result = add_credit("MultiCredit", amount=30000)
        assert result["customer"]["balance"] == 50000

    def test_add_credit_with_bill_id(self):
        from kirana.tools.billing import create_bill
        bill = create_bill()["bill"]
        get_or_create_customer("BillCredit")
        result = add_credit("BillCredit", amount=15000, bill_id=bill["id"])
        assert result["transaction"]["bill_id"] == bill["id"]

    def test_add_credit_with_note(self):
        get_or_create_customer("NoteCredit")
        result = add_credit("NoteCredit", amount=10000, note="Diwali sweets")
        assert result["transaction"]["note"] == "Diwali sweets"

    def test_add_credit_nonexistent_customer(self):
        result = add_credit("NoOne", amount=10000)
        assert "error" in result

    def test_add_credit_negative_amount(self):
        get_or_create_customer("NegTest")
        result = add_credit("NegTest", amount=-500)
        assert "error" in result

    def test_add_credit_zero_amount(self):
        get_or_create_customer("ZeroTest")
        result = add_credit("ZeroTest", amount=0)
        assert "error" in result


# ---------------------------------------------------------------------------
# settle_credit
# ---------------------------------------------------------------------------

class TestSettleCredit:
    def test_settle_full_balance(self):
        get_or_create_customer("FullSettle")
        add_credit("FullSettle", amount=30000)
        result = settle_credit("FullSettle", amount=30000)
        assert result["customer"]["balance"] == 0
        assert result["transaction"]["txn_type"] == "settle"

    def test_settle_partial(self):
        get_or_create_customer("PartialSettle")
        add_credit("PartialSettle", amount=50000)
        result = settle_credit("PartialSettle", amount=20000)
        assert result["customer"]["balance"] == 30000

    def test_settle_exceeding_balance_refused(self):
        get_or_create_customer("ExceedSettle")
        add_credit("ExceedSettle", amount=10000)
        result = settle_credit("ExceedSettle", amount=20000)
        assert "error" in result
        assert "exceeds" in result["error"].lower()

    def test_settle_nonexistent_customer(self):
        result = settle_credit("Ghost", amount=5000)
        assert "error" in result

    def test_settle_with_payment_mode_and_note(self):
        get_or_create_customer("PmtSettle")
        add_credit("PmtSettle", amount=10000)
        result = settle_credit("PmtSettle", amount=10000, payment_mode="upi", note="Full payment")
        assert result["transaction"]["payment_mode"] == "upi"
        assert result["transaction"]["note"] == "Full payment"

    def test_settle_negative_amount(self):
        get_or_create_customer("NegSettle")
        add_credit("NegSettle", amount=10000)
        result = settle_credit("NegSettle", amount=-1000)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

class TestGetBalance:
    def test_get_balance_zero_for_new(self):
        get_or_create_customer("BalTest")
        result = get_balance("BalTest")
        assert result["customer"]["balance"] == 0

    def test_get_balance_after_credit(self):
        get_or_create_customer("BalCredit")
        add_credit("BalCredit", amount=75000)
        result = get_balance("BalCredit")
        assert result["customer"]["balance"] == 75000

    def test_get_balance_nonexistent(self):
        result = get_balance("NoSuchCustomer")
        assert "error" in result


# ---------------------------------------------------------------------------
# list_khata
# ---------------------------------------------------------------------------

class TestListKhata:
    def test_list_with_customers(self):
        get_or_create_customer("Alice")
        get_or_create_customer("Bob")
        result = list_khata()
        assert result["count"] >= 2
        names = [c["name"] for c in result["customers"]]
        assert "Alice" in names
        assert "Bob" in names

    def test_list_sorted_by_balance_desc(self):
        get_or_create_customer("Rich")
        get_or_create_customer("Poor")
        add_credit("Rich", amount=50000)
        add_credit("Poor", amount=10000)
        result = list_khata()
        balances = [c["balance"] for c in result["customers"] if c["name"] in ("Rich", "Poor")]
        assert balances == sorted(balances, reverse=True)
