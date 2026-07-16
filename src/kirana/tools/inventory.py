"""Inventory tools — first tools the agent uses to manage products and stock.

All cost/sell/MRP prices are in **paise** (₹1 = 100 paise).
The agent converts from rupees: ₹14 → 1400 paise.
"""

from sqlalchemy import and_
from kirana.db.connection import get_session
from kirana.db.models import Product, StockMovement
from kirana.repo import product_repo


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _product_to_dict(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "unit_size": product.unit_size,
        "unit_type": product.unit_type,
        "is_loose": product.is_loose,
        "cost_price": product.cost_price,
        "sell_price": product.sell_price,
        "mrp": product.mrp,
        "gst_slab": product.gst_slab,
        "hsn_code": product.hsn_code,
        "quantity": product.quantity,
        "reorder_level": product.reorder_level,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


def _fmt_price(paise: int) -> str:
    """Format paise to ₹ string, e.g. 1400 → '₹14'."""
    return f"₹{paise // 100}.{paise % 100:02d}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def search_products(query: str) -> dict:
    """Search the product catalog by name or brand.
    Returns matching products with current stock and prices.

    Args:
        query: Product name or brand to search for, e.g. 'sugar', 'atta', 'Maggi'
    """
    results = product_repo.search(query)
    return {
        "products": results,
        "count": len(results),
        "message": f"Found {len(results)} match(es)." if results
                   else f"No products found matching '{query}'."
    }


def add_product(
    name: str,
    brand: str | None = None,
    unit_size: float | None = None,
    unit_type: str = "piece",
    is_loose: bool = False,
    cost_price: int = 0,
    sell_price: int = 0,
    mrp: int | None = None,
    gst_slab: int = 0,
    hsn_code: str = "",
    reorder_level: float = 0,
) -> dict:
    """Register a new SKU in the product catalog.

    All prices in **paise** (₹1 = 100 paise). The agent converts from rupees:
    ₹14 → 1400 paise.

    Args:
        name: Product name, e.g. 'Amul Butter'
        brand: Brand name (optional, None for loose items)
        unit_size: Package size, e.g. 100 for 100g, 5 for 5kg
        unit_type: Unit type — kg, g, L, ml, piece, packet, dozen
        is_loose: True if sold by weight (loose), False if packaged
        cost_price: Cost price in paise
        sell_price: Selling price in paise
        mrp: MRP in paise (optional)
        gst_slab: GST slab rate — must be 0, 5, 12, or 18
        hsn_code: HSN code (non-empty)
        reorder_level: Stock level that triggers low-stock alert
    """
    # --- Guardrails ---
    if gst_slab not in (0, 5, 12, 18):
        return {"error": f"Invalid GST slab {gst_slab}. Must be 0, 5, 12, or 18."}

    if not hsn_code or not hsn_code.strip():
        return {"error": "HSN code is required and cannot be empty."}

    if sell_price < cost_price:
        return {
            "error": (
                f"Sell price {_fmt_price(sell_price)} is below "
                f"cost price {_fmt_price(cost_price)}. Cannot add."
            )
        }

    if not name or not name.strip():
        return {"error": "Product name is required."}

    # --- Insert (with duplicate check in same transaction) ---
    with get_session() as session:
        # Exact-match duplicate check
        conditions = [Product.name == name, Product.unit_size == unit_size, Product.unit_type == unit_type]
        if brand is None:
            conditions.append(Product.brand.is_(None))
        else:
            conditions.append(Product.brand == brand)
        duplicate = session.query(Product).filter(and_(*conditions)).first()
        if duplicate:
            brand_label = f" ({brand})" if brand else ""
            return {
                "error": (
                    f"Product '{name}{brand_label}' with {unit_size}{unit_type} "
                    f"already exists (id={duplicate.id})."
                )
            }

        product = Product(
            name=name,
            brand=brand,
            unit_size=unit_size,
            unit_type=unit_type,
            is_loose=is_loose,
            cost_price=cost_price,
            sell_price=sell_price,
            mrp=mrp,
            gst_slab=gst_slab,
            hsn_code=hsn_code,
            quantity=0.0,
            reorder_level=reorder_level,
        )
        session.add(product)
        session.flush()
        product_dict = _product_to_dict(product)

    brand_label = f" {brand}" if brand else ""
    size_desc = f"{unit_size}{unit_type} per pack" if unit_size else unit_type
    return {
        "product": product_dict,
        "message": (
            f"Added product '{name}{brand_label}' — "
            f"unit size: {size_desc}, sell price: {_fmt_price(sell_price)}. "
            f"Current stock: 0 (use receive_stock to add inventory)."
        ),
    }


def receive_stock(
    product_id: int,
    quantity: float,
    cost_price: int | None = None,
) -> dict:
    """Record incoming stock. Atomically increments quantity and logs movement.

    All prices in **paise** (₹1 = 100 paise).

    Args:
        product_id: ID of the product
        quantity: Quantity received (must be > 0)
        cost_price: New cost price in paise (optional, updates product if provided)
    """
    if quantity <= 0:
        return {"error": f"Quantity must be positive, got {quantity}."}

    with get_session() as session:
        product = (
            session.query(Product)
            .filter(Product.id == product_id)
            .with_for_update()
            .first()
        )
        if not product:
            return {"error": f"Product with id {product_id} not found."}

        product.quantity += quantity

        movement = StockMovement(
            product_id=product_id,
            movement_type="in",
            quantity=quantity,
            cost_price=cost_price,
        )
        session.add(movement)

        if cost_price is not None:
            product.cost_price = cost_price

        session.flush()
        product_dict = _product_to_dict(product)

    return {
        "product": product_dict,
        "message": f"Received {quantity} of {product.name}. New stock: {product.quantity}.",
    }


def get_stock(product_id: int) -> dict:
    """Query current stock, price, and reorder level for a product.

    Args:
        product_id: ID of the product
    """
    product = product_repo.get_by_id(product_id)
    if not product:
        return {"error": f"Product with id {product_id} not found."}

    label = f"{product['name']}"
    if product.get("brand"):
        label = f"{product['brand']} {label}"
    return {
        "product": product,
        "message": (
            f"{label}: {product['quantity']}{product['unit_type']} in stock, "
            f"sell price {_fmt_price(product['sell_price'])}/{product['unit_type']}."
        ),
    }


def get_low_stock() -> dict:
    """Return all products at or below their reorder level."""
    products = product_repo.get_low_stock()
    if not products:
        return {
            "products": [],
            "count": 0,
            "message": "No items are low on stock."
        }

    items = []
    for p in products:
        label = p["name"]
        if p.get("brand"):
            label = f"{p['brand']} {label}"
        items.append(f"{label} ({p['quantity']}/{p['reorder_level']})")

    return {
        "products": products,
        "count": len(products),
        "message": f"{len(products)} items low: {', '.join(items)}."
    }


def adjust_stock(
    product_id: int,
    new_quantity: float,
    reason: str,
) -> dict:
    """Explicitly correct stock level (damage, theft, miscount).
    Requires a reason which is logged in stock_movements.

    Args:
        product_id: ID of the product
        new_quantity: New stock quantity (must be >= 0)
        reason: Reason for adjustment (required, logged in audit trail)
    """
    if not reason or not reason.strip():
        return {"error": "Reason is required for stock adjustment."}

    if new_quantity < 0:
        return {"error": f"New quantity cannot be negative, got {new_quantity}."}

    with get_session() as session:
        product = (
            session.query(Product)
            .filter(Product.id == product_id)
            .with_for_update()
            .first()
        )
        if not product:
            return {"error": f"Product with id {product_id} not found."}

        old_qty = product.quantity
        delta = new_quantity - old_qty
        product.quantity = new_quantity

        movement = StockMovement(
            product_id=product_id,
            movement_type="adjustment",
            quantity=delta,
            reference=reason,
        )
        session.add(movement)
        session.flush()
        product_dict = _product_to_dict(product)

    return {
        "product": product_dict,
        "message": (
            f"Adjusted {product.name} stock from {old_qty} to {new_quantity}. "
            f"Reason: {reason}."
        ),
    }
