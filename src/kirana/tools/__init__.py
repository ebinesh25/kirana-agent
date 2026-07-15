from .inventory import (
    search_products, add_product, receive_stock,
    get_stock, get_low_stock, adjust_stock,
)
from .billing import (
    create_bill, add_item, update_item, remove_item,
    get_bill, finalize_bill, cancel_bill,
)
from .khata import (
    get_or_create_customer, add_credit, settle_credit,
    get_balance, list_khata,
)
from .analytics import (
    get_daily_summary, get_sales_analysis, get_inventory_value,
)
from .memory import (
    set_preference, get_preferences, delete_preference,
)
from .documents import (
    generate_invoice_pdf, generate_analysis_pptx,
)


def get_all_tools():
    """Return all tool functions for Agent(tools=[...]) registration."""
    return [
        search_products, add_product, receive_stock,
        get_stock, get_low_stock, adjust_stock,
        create_bill, add_item, update_item, remove_item,
        get_bill, finalize_bill, cancel_bill,
        get_or_create_customer, add_credit, settle_credit,
        get_balance, list_khata,
        get_daily_summary, get_sales_analysis, get_inventory_value,
        set_preference, get_preferences, delete_preference,
        generate_invoice_pdf, generate_analysis_pptx,
    ]
