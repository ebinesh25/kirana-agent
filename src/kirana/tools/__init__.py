from .inventory import (
    search_products, add_product, receive_stock,
    get_stock, get_low_stock, adjust_stock,
)
# Phase 3+ will add billing, khata, analytics, documents, memory tools here


def get_all_tools():
    """Return all tool functions for Agent(tools=[...]) registration."""
    return [
        search_products, add_product, receive_stock,
        get_stock, get_low_stock, adjust_stock,
    ]
