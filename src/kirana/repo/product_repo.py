from sqlalchemy import text, or_
from kirana.db.connection import get_session
from kirana.db.models import Product


def _row_to_dict(product: Product) -> dict:
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
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def _search_terms(query: str) -> list[str]:
    """Generate search term variations for basic singular/plural matching."""
    terms = [query]
    if query.lower().endswith("ies") and len(query) > 4:
        terms.append(query[:-3] + "y")     # berries → berry
    elif query.lower().endswith("s") and not query.lower().endswith("ss") and len(query) > 3:
        terms.append(query[:-1])            # biscuits → biscuit, attas → atta
    else:
        terms.append(query + "s")           # biscuit → biscuits
        if query.lower().endswith("y") and len(query) > 3:
            terms.append(query[:-1] + "ies")  # berry → berries
    return list(set(terms))


def get_by_id(product_id: int) -> dict | None:
    with get_session() as session:
        product = session.query(Product).filter(Product.id == product_id).first()
        return _row_to_dict(product) if product else None


def search(query: str) -> list[dict]:
    with get_session() as session:
        terms = _search_terms(query)
        conditions = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.append(Product.name.ilike(pattern))
            conditions.append(Product.brand.ilike(pattern))
        products = (
            session.query(Product)
            .filter(or_(*conditions))
            .all()
        )
        return [_row_to_dict(p) for p in products]


def get_all() -> list[dict]:
    with get_session() as session:
        products = session.query(Product).all()
        return [_row_to_dict(p) for p in products]


def create(
    name: str,
    unit_type: str,
    cost_price: int,
    sell_price: int,
    gst_slab: int,
    hsn_code: str,
    brand: str | None = None,
    unit_size: float | None = None,
    is_loose: bool = False,
    mrp: int | None = None,
    quantity: float = 0,
    reorder_level: float = 0,
) -> dict:
    with get_session() as session:
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
            quantity=quantity,
            reorder_level=reorder_level,
        )
        session.add(product)
        session.flush()
        return _row_to_dict(product)


def update_quantity(product_id: int, delta: float) -> dict:
    with get_session() as session:
        product = session.query(Product).filter(Product.id == product_id).with_for_update().one()
        product.quantity += delta
        session.flush()
        return _row_to_dict(product)


def update_prices(
    product_id: int,
    cost_price: int | None = None,
    sell_price: int | None = None,
    mrp: int | None = None,
) -> dict:
    with get_session() as session:
        product = session.query(Product).filter(Product.id == product_id).one()
        if cost_price is not None:
            product.cost_price = cost_price
        if sell_price is not None:
            product.sell_price = sell_price
        if mrp is not None:
            product.mrp = mrp
        session.flush()
        return _row_to_dict(product)


def get_low_stock() -> list[dict]:
    with get_session() as session:
        products = (
            session.query(Product)
            .filter(Product.quantity <= Product.reorder_level)
            .all()
        )
        return [_row_to_dict(p) for p in products]
