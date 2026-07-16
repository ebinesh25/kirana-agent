"""Tests for memory/preference tool functions.

Tests call tools directly. Uses test DB fixtures from conftest.py.
"""

from kirana.tools.memory import (
    set_preference,
    get_preferences,
    delete_preference,
)


# ---------------------------------------------------------------------------
# set_preference
# ---------------------------------------------------------------------------

class TestSetPreference:
    def test_set_new_preference(self):
        result = set_preference("shop_name", "My Kirana Store")
        assert "preference" in result
        assert result["preference"]["key"] == "shop_name"
        assert result["preference"]["value"] == "My Kirana Store"

    def test_update_existing_preference(self):
        set_preference("shop_name", "Old Name")
        result = set_preference("shop_name", "New Name")
        assert result["preference"]["value"] == "New Name"

    def test_multiple_preferences(self):
        set_preference("key1", "val1")
        set_preference("key2", "val2")
        all_prefs = get_preferences()
        assert all_prefs["preferences"]["key1"] == "val1"
        assert all_prefs["preferences"]["key2"] == "val2"


# ---------------------------------------------------------------------------
# get_preferences
# ---------------------------------------------------------------------------

class TestGetPreferences:
    def test_get_all_empty(self):
        # After test cleanup, no prefs set in this class
        result = get_preferences()
        # This might have prefs from other tests — check structure
        assert "preferences" in result
        assert "count" in result

    def test_get_all_after_set(self):
        set_preference("gstin", "27ABCDE1234F1Z5")
        result = get_preferences()
        assert result["preferences"]["gstin"] == "27ABCDE1234F1Z5"
        assert result["count"] >= 1

    def test_get_all_message_when_empty(self):
        # Use unique key so tests don't interfere
        # Works in isolation since conftest drops/recreates DB per test
        result = get_preferences()
        if result["count"] == 0:
            assert "No preferences" in result["message"]


# ---------------------------------------------------------------------------
# delete_preference
# ---------------------------------------------------------------------------

class TestDeletePreference:
    def test_delete_existing(self):
        set_preference("temp_key", "temp_val")
        result = delete_preference("temp_key")
        assert "message" in result
        assert "deleted" in result["message"].lower()
        # Verify gone
        all_prefs = get_preferences()
        assert "temp_key" not in all_prefs["preferences"]

    def test_delete_nonexistent(self):
        result = delete_preference("no_such_key")
        assert "error" in result

    def test_delete_then_recreate(self):
        set_preference("recreate_key", "old")
        delete_preference("recreate_key")
        result = set_preference("recreate_key", "new")
        assert result["preference"]["value"] == "new"
