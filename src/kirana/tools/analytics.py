"""Analytics & daily-close tools for Phase 4.

Provides business intelligence: daily summaries, sales trends, inventory valuation.
All monetary values in paise.
"""

from datetime import date, datetime, timedelta
from sqlalchemy import func
from kirana.db.connection import get_session
from kirana.db.models import Bill, BillItem, Product


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fmt_price(paise: int) -> str:
    return f"\u20b9{paise // 100}.{paise % 100:02d}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def get_daily_summary(target_date: str | None = None) -> dict:
    """End-of-day summary for a given date.

    Computes: total sales, bill count, avg bill value, payment breakdown,
    top-selling items, GST collected (by slab).

    Args:
        target_date: Date string in YYYY-MM-DD format. Defaults to today.
    """
    if target_date:
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            return {"error": f"Invalid date '{target_date}'. Use YYYY-MM-DD format."}
    else:
        dt = datetime.utcnow()

    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    with get_session() as session:
        bills = (
            session.query(Bill)
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= day_start,
                Bill.finalized_at < day_end,
            )
            .all()
        )

        total_sales = sum(b.grand_total for b in bills)
        bill_count = len(bills)
        avg_bill = total_sales // bill_count if bill_count else 0

        # Payment mode breakdown
        pmt: dict[str, int] = {}
        for b in bills:
            mode = b.payment_mode or "unknown"
            pmt[mode] = pmt.get(mode, 0) + b.grand_total

        # Top items by quantity
        item_rows = (
            session.query(
                BillItem.product_name_snapshot,
                func.sum(BillItem.quantity).label("total_qty"),
                func.sum(BillItem.line_total).label("total_revenue"),
            )
            .join(Bill)
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= day_start,
                Bill.finalized_at < day_end,
            )
            .group_by(BillItem.product_name_snapshot)
            .order_by(func.sum(BillItem.quantity).desc())
            .limit(10)
            .all()
        )

        top_items = [
            {
                "product": r.product_name_snapshot,
                "quantity": float(r.total_qty),
                "revenue": int(r.total_revenue),
            }
            for r in item_rows
        ]

        # GST by slab
        gst_rows = (
            session.query(
                BillItem.gst_slab,
                func.sum(BillItem.cgst_amount + BillItem.sgst_amount).label("total_gst"),
                func.sum(BillItem.quantity * BillItem.sell_price).label("total_taxable"),
            )
            .join(Bill)
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= day_start,
                Bill.finalized_at < day_end,
            )
            .group_by(BillItem.gst_slab)
            .all()
        )

        gst_by_slab = [
            {
                "gst_slab": r.gst_slab,
                "taxable": int(r.total_taxable),
                "gst_collected": int(r.total_gst),
            }
            for r in gst_rows
        ]

    date_label = dt.strftime("%Y-%m-%d")
    return {
        "date": date_label,
        "total_sales": total_sales,
        "bill_count": bill_count,
        "avg_bill_value": avg_bill,
        "payment_breakdown": pmt,
        "top_items": top_items,
        "gst_by_slab": gst_by_slab,
        "message": (
            f"Summary for {date_label}: {bill_count} bill(s), "
            f"total {_fmt_price(total_sales)}, "
            f"avg {_fmt_price(avg_bill)} per bill."
        ),
    }


def get_sales_analysis(start_date: str, end_date: str) -> dict:
    """Analyse sales over a date range.

    Provides: total sales, bill count, daily trend, top items,
    payment distribution, GST by slab.

    Args:
        start_date: Start date YYYY-MM-DD (inclusive)
        end_date: End date YYYY-MM-DD (inclusive)
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # exclusive end
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    if start_dt >= end_dt:
        return {"error": "start_date must be before end_date."}

    with get_session() as session:
        bills = (
            session.query(Bill)
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= start_dt,
                Bill.finalized_at < end_dt,
            )
            .all()
        )

        total_sales = sum(b.grand_total for b in bills)
        bill_count = len(bills)
        avg_bill = total_sales // bill_count if bill_count else 0

        # Daily trend
        daily_data = (
            session.query(
                func.date(Bill.finalized_at).label("day"),
                func.count(Bill.id).label("bill_count"),
                func.sum(Bill.grand_total).label("daily_total"),
            )
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= start_dt,
                Bill.finalized_at < end_dt,
            )
            .group_by(func.date(Bill.finalized_at))
            .order_by(func.date(Bill.finalized_at))
            .all()
        )

        daily_trend = [
            {
                "date": str(r.day),
                "bill_count": r.bill_count,
                "total": int(r.daily_total),
            }
            for r in daily_data
        ]

        # Payment distribution
        pmt: dict[str, int] = {}
        for b in bills:
            mode = b.payment_mode or "unknown"
            pmt[mode] = pmt.get(mode, 0) + b.grand_total

        # Top items
        item_rows = (
            session.query(
                BillItem.product_name_snapshot,
                func.sum(BillItem.quantity).label("total_qty"),
                func.sum(BillItem.line_total).label("total_revenue"),
            )
            .join(Bill)
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= start_dt,
                Bill.finalized_at < end_dt,
            )
            .group_by(BillItem.product_name_snapshot)
            .order_by(func.sum(BillItem.line_total).desc())
            .limit(10)
            .all()
        )

        top_items = [
            {
                "product": r.product_name_snapshot,
                "quantity": float(r.total_qty),
                "revenue": int(r.total_revenue),
            }
            for r in item_rows
        ]

        # GST by slab
        gst_rows = (
            session.query(
                BillItem.gst_slab,
                func.sum(BillItem.cgst_amount + BillItem.sgst_amount).label("total_gst"),
                func.sum(BillItem.quantity * BillItem.sell_price).label("total_taxable"),
            )
            .join(Bill)
            .filter(
                Bill.status == "finalized",
                Bill.finalized_at >= start_dt,
                Bill.finalized_at < end_dt,
            )
            .group_by(BillItem.gst_slab)
            .all()
        )

        gst_by_slab = [
            {
                "gst_slab": r.gst_slab,
                "taxable": int(r.total_taxable),
                "gst_collected": int(r.total_gst),
            }
            for r in gst_rows
        ]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "period_summary": {
            "total_sales": total_sales,
            "bill_count": bill_count,
            "avg_bill_value": avg_bill,
        },
        "daily_trend": daily_trend,
        "payment_distribution": pmt,
        "top_items": top_items,
        "gst_by_slab": gst_by_slab,
        "message": (
            f"Sales from {start_date} to {end_date}: "
            f"{bill_count} bill(s), total {_fmt_price(total_sales)}."
        ),
    }


def get_inventory_value() -> dict:
    """Compute total inventory valuation at cost and retail (sell) prices.

    Returns: total products, cost value, retail value, and individual items.
    """
    with get_session() as session:
        products = session.query(Product).all()

        total_cost = sum(p.quantity * p.cost_price for p in products)
        total_retail = sum(p.quantity * p.sell_price for p in products)
        product_count = len(products)

        items = [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "quantity": p.quantity,
                "cost_price": p.cost_price,
                "sell_price": p.sell_price,
                "reorder_level": p.reorder_level,
                "cost_value": int(p.quantity * p.cost_price),
                "retail_value": int(p.quantity * p.sell_price),
            }
            for p in products
        ]
        items.sort(key=lambda x: x["retail_value"], reverse=True)

    return {
        "product_count": product_count,
        "total_cost_value": int(total_cost),
        "total_retail_value": int(total_retail),
        "items": items,
        "message": (
            f"{product_count} products — "
            f"cost: {_fmt_price(int(total_cost))}, "
            f"retail: {_fmt_price(int(total_retail))}."
        ),
    }
