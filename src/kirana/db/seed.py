from kirana.db.connection import get_session
from kirana.db.models import Product


SEED_PRODUCTS = [
    {"name": "Aashirvaad Atta", "brand": "Aashirvaad", "unit_size": 5, "unit_type": "kg", "is_loose": False, "cost_price": 22000, "sell_price": 26000, "mrp": 26000, "gst_slab": 5, "hsn_code": "1101", "quantity": 20, "reorder_level": 5},
    {"name": "Tata Salt", "brand": "Tata", "unit_size": 1, "unit_type": "kg", "is_loose": False, "cost_price": 2400, "sell_price": 2800, "mrp": 2800, "gst_slab": 0, "hsn_code": "2501", "quantity": 30, "reorder_level": 8},
    {"name": "Amul Butter", "brand": "Amul", "unit_size": 100, "unit_type": "g", "is_loose": False, "cost_price": 5200, "sell_price": 6200, "mrp": 6200, "gst_slab": 12, "hsn_code": "0405", "quantity": 15, "reorder_level": 5},
    {"name": "Fortune Sunflower Oil", "brand": "Fortune", "unit_size": 1, "unit_type": "L", "is_loose": False, "cost_price": 11000, "sell_price": 13500, "mrp": 13500, "gst_slab": 5, "hsn_code": "1512", "quantity": 18, "reorder_level": 5},
    {"name": "Maggi Noodles", "brand": "Maggi", "unit_size": 70, "unit_type": "g", "is_loose": False, "cost_price": 1200, "sell_price": 1400, "mrp": 1400, "gst_slab": 12, "hsn_code": "1902", "quantity": 48, "reorder_level": 12},
    {"name": "Parle-G Biscuit", "brand": "Parle", "unit_size": 100, "unit_type": "g", "is_loose": False, "cost_price": 500, "sell_price": 800, "mrp": 800, "gst_slab": 12, "hsn_code": "1905", "quantity": 40, "reorder_level": 10},
    {"name": "Surf Excel", "brand": "Surf Excel", "unit_size": 1, "unit_type": "kg", "is_loose": False, "cost_price": 9500, "sell_price": 12000, "mrp": 12000, "gst_slab": 18, "hsn_code": "3402", "quantity": 10, "reorder_level": 3},
    {"name": "Sugar (loose)", "brand": None, "unit_size": 1, "unit_type": "kg", "is_loose": True, "cost_price": 3800, "sell_price": 4500, "mrp": 4500, "gst_slab": 5, "hsn_code": "1701", "quantity": 25, "reorder_level": 5},
    {"name": "Rice (loose)", "brand": None, "unit_size": 1, "unit_type": "kg", "is_loose": True, "cost_price": 4500, "sell_price": 5500, "mrp": 5500, "gst_slab": 0, "hsn_code": "1006", "quantity": 40, "reorder_level": 10},
    {"name": "Toor Dal (loose)", "brand": None, "unit_size": 1, "unit_type": "kg", "is_loose": True, "cost_price": 9000, "sell_price": 11000, "mrp": 11000, "gst_slab": 0, "hsn_code": "0713", "quantity": 15, "reorder_level": 5},
    {"name": "Loose Atta", "brand": None, "unit_size": 1, "unit_type": "kg", "is_loose": True, "cost_price": 3500, "sell_price": 4200, "mrp": 4200, "gst_slab": 0, "hsn_code": "1101", "quantity": 20, "reorder_level": 5},
    {"name": "Tea (loose)", "brand": None, "unit_size": 1, "unit_type": "kg", "is_loose": True, "cost_price": 18000, "sell_price": 22000, "mrp": 22000, "gst_slab": 5, "hsn_code": "0902", "quantity": 8, "reorder_level": 3},
]


def run_seed():
    with get_session() as session:
        existing = session.query(Product).count()
        if existing > 0:
            return
        for data in SEED_PRODUCTS:
            product = Product(**data)
            session.add(product)
