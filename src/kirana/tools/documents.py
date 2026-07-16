"""Document generation tools — PDF invoices and PPTX analysis decks.

Produces real artifacts (hard part #8): GST-correct PDF invoices via WeasyPrint
and business-analysis PowerPoint decks with embedded matplotlib charts.
"""

import os
from datetime import datetime, timedelta, date
from pathlib import Path

from kirana.config import settings
from kirana.db.connection import get_session
from kirana.db.models import Bill, BillItem
from kirana.repo import preference_repo
from kirana.tools.analytics import get_sales_analysis, get_inventory_value

OUTPUT_DIR = Path(settings.OUTPUT_DIR)

def _ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def _fmt_price(paise: int) -> str:
    return f"\u20b9{paise // 100}.{paise % 100:02d}"

def _load_bill(bill_id: int) -> tuple[Bill | None, list[BillItem] | None, str | None]:
    with get_session() as session:
        bill = session.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return None, None, f"Bill with id {bill_id} not found."
        if bill.status != "finalized":
            return None, None, f"Bill {bill.bill_number} is still a draft — finalize it first."
        items = session.query(BillItem).filter(BillItem.bill_id == bill_id).all()
        return bill, items, None


def generate_invoice_pdf(bill_id: int) -> dict:
    """Generate a GST-correct PDF invoice for a finalized bill.

    Fetches bill + items from DB, loads shop preferences (name, GSTIN, address),
    renders an HTML template through WeasyPrint, and saves to OUTPUT_DIR.

    Args:
        bill_id: ID of the finalized bill
    """
    from weasyprint import HTML
    from jinja2 import Template

    _ensure_output_dir()
    bill, items, error = _load_bill(bill_id)
    if error:
        return {"error": error}

    prefs = preference_repo.get_all()
    shop_name = prefs.get("shop_name", "Kirana Store")
    gstin = prefs.get("gstin", "Not registered")
    shop_address = prefs.get("shop_address", "")

    rows = []
    for item in items:
        rows.append({
            "name": item.product_name_snapshot,
            "hsn": item.hsn_code,
            "qty": f"{item.quantity}{item.unit_snapshot}" if item.unit_snapshot else str(item.quantity),
            "rate": _fmt_price(item.sell_price),
            "gst_slab": item.gst_slab,
            "cgst": _fmt_price(item.cgst_amount),
            "sgst": _fmt_price(item.sgst_amount),
            "amount": _fmt_price(item.line_total),
        })

    totals = {
        "subtotal": _fmt_price(bill.subtotal),
        "total_cgst": _fmt_price(bill.total_cgst),
        "total_sgst": _fmt_price(bill.total_sgst),
        "total_tax": _fmt_price(bill.total_tax),
        "round_off": _fmt_price(bill.round_off),
        "grand_total": _fmt_price(bill.grand_total),
    }

    date_str = bill.finalized_at.strftime("%d-%b-%Y") if bill.finalized_at else datetime.utcnow().strftime("%d-%b-%Y")
    payment_str = f"{bill.payment_mode or 'N/A'}"
    if bill.payment_ref:
        payment_str += f" (Ref: {bill.payment_ref})"

    template_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page { margin: 20mm 15mm; }
  body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 11px; color: #333; }
  .header { text-align: center; margin-bottom: 18px; }
  .shop-name { font-size: 20px; font-weight: bold; color: #1a237e; }
  .shop-addr { font-size: 10px; color: #666; margin-top: 2px; }
  .gstin { font-size: 10px; color: #555; margin-top: 2px; }
  hr { border: none; border-top: 2px solid #1a237e; margin: 10px 0; }
  h3 { margin: 6px 0; font-size: 14px; }
  .meta { font-size: 10px; margin: 6px 0; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0; }
  th, td { border: 1px solid #ccc; padding: 5px 6px; text-align: left; }
  th { background: #e8eaf6; font-size: 10px; }
  td { font-size: 10px; }
  .num { text-align: right; }
  .totals { margin-left: auto; width: 260px; }
  .totals td { border: none; padding: 3px 6px; }
  .totals tr:last-child td { font-weight: bold; font-size: 12px; border-top: 2px solid #333; padding-top: 6px; }
  .footer { text-align: center; font-size: 10px; color: #888; margin-top: 20px; }
</style>
</head>
<body>
<div class="header">
  <div class="shop-name">{{ shop_name }}</div>
  {% if shop_address %}<div class="shop-addr">{{ shop_address }}</div>{% endif %}
  <div class="gstin">GSTIN: {{ gstin }}</div>
</div>
<hr>
<h3>Tax Invoice</h3>
<p class="meta">Bill No: {{ bill_number }} | Date: {{ date }} | Payment: {{ payment_mode }}</p>
<table>
  <tr>
    <th>#</th><th>Item</th><th>HSN</th><th>Qty</th><th>Rate</th>
    <th>Tax%</th><th class="num">CGST</th><th class="num">SGST</th><th class="num">Amount</th>
  </tr>
  {% for item in items %}
  <tr>
    <td>{{ loop.index }}</td>
    <td>{{ item.name }}</td>
    <td>{{ item.hsn }}</td>
    <td>{{ item.qty }}</td>
    <td class="num">{{ item.rate }}</td>
    <td class="num">{{ item.gst_slab }}%</td>
    <td class="num">{{ item.cgst }}</td>
    <td class="num">{{ item.sgst }}</td>
    <td class="num">{{ item.amount }}</td>
  </tr>
  {% endfor %}
</table>
<table class="totals">
  <tr><td>Subtotal</td><td class="num">{{ totals.subtotal }}</td></tr>
  <tr><td>CGST</td><td class="num">{{ totals.total_cgst }}</td></tr>
  <tr><td>SGST</td><td class="num">{{ totals.total_sgst }}</td></tr>
  <tr><td>Total Tax</td><td class="num">{{ totals.total_tax }}</td></tr>
  <tr><td>Round Off</td><td class="num">{{ totals.round_off }}</td></tr>
  <tr><td>Grand Total</td><td class="num">{{ totals.grand_total }}</td></tr>
</table>
<div class="footer">Thank you for shopping with us!</div>
</body>
</html>"""

    template = Template(template_html)
    html_str = template.render(
        shop_name=shop_name,
        shop_address=shop_address,
        gstin=gstin,
        bill_number=bill.bill_number,
        date=date_str,
        payment_mode=payment_str,
        items=rows,
        totals=totals,
    )

    file_path = OUTPUT_DIR / f"invoice_{bill.bill_number}.pdf"
    HTML(string=html_str).write_pdf(str(file_path))

    return {
        "file_path": str(file_path),
        "bill_number": bill.bill_number,
        "message": f"Invoice {bill.bill_number} ready.",
    }


def generate_analysis_pptx(period: str = "week") -> dict:
    """Generate a PowerPoint sales analysis deck with real charts.

    Calls analytics tools for data, renders matplotlib charts, and embeds
    them in a python-pptx presentation with insight bullets.

    Args:
        period: Analysis period — 'week' (last 7 days), 'month' (last 30 days),
                or a date range 'START:END' (YYYY-MM-DD:YYYY-MM-DD)
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor

    _ensure_output_dir()

    today = date.today()
    if period == "week":
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
    elif period == "month":
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()
    elif ":" in period:
        parts = period.split(":", 1)
        start, end = parts[0].strip(), parts[1].strip()
    else:
        return {"error": f"Invalid period '{period}'. Use 'week', 'month', or 'START_DATE:END_DATE'."}

    analysis = get_sales_analysis(start, end)
    if "error" in analysis:
        return {"error": analysis["error"]}

    inventory = get_inventory_value()
    prefs = preference_repo.get_all()
    shop_name = prefs.get("shop_name", "Kirana Store")

    prs = Presentation()
    blank_layout = prs.slide_layouts[6]

    # Helper
    def add_title(slide, text, top=Inches(0.3)):
        from pptx.util import Pt
        txBox = slide.shapes.add_textbox(Inches(0.5), top, Inches(9), Inches(0.5))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(28)
        p.font.bold = True

    def add_bullets(slide, bullets, top=Inches(5.5)):
        txBox = slide.shapes.add_textbox(Inches(0.5), top, Inches(9), Inches(1.0))
        tf = txBox.text_frame
        for i, b in enumerate(bullets):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = b
            p.font.size = Pt(13)
            p.space_after = Pt(4)

    # --- Slide 1: Title ---
    slide1 = prs.slides.add_slide(blank_layout)
    txBox = slide1.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(3))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = f"Sales Analysis"
    p.font.size = Pt(40)
    p.font.bold = True
    p = tf.add_paragraph()
    p.text = f"{start} to {end}"
    p.font.size = Pt(24)
    p.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    p = tf.add_paragraph()
    p.text = shop_name
    p.font.size = Pt(18)
    p.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    summary = analysis.get("period_summary", {})
    total_sales = summary.get("total_sales", 0)
    bill_count = summary.get("bill_count", 0)
    avg_bill = summary.get("avg_bill_value", 0)
    daily_trend = analysis.get("daily_trend", [])
    top_items = analysis.get("top_items", [])
    payment_dist = analysis.get("payment_distribution", {})
    gst_by_slab = analysis.get("gst_by_slab", [])
    inv_items = inventory.get("items", [])
    low_stock = [i for i in inv_items if i["quantity"] <= i.get("reorder_level", 5)]

    # --- Slide 2: Overview ---
    slide2 = prs.slides.add_slide(blank_layout)
    add_title(slide2, "Overview & Key Metrics")

    metrics = [
        f"Total Revenue: {_fmt_price(total_sales)}",
        f"Total Bills: {bill_count}",
        f"Average Bill Value: {_fmt_price(avg_bill)}",
        f"Total GST Collected: {_fmt_price(sum(g['gst_collected'] for g in gst_by_slab))}",
        f"Products in Stock: {inventory.get('product_count', 0)}",
        f"Low Stock Items: {len(low_stock)}",
    ]
    if len(daily_trend) >= 2:
        best = max(daily_trend, key=lambda d: d["total"])
        worst = min(daily_trend, key=lambda d: d["total"])
        metrics.append(f"Best Day: {best['date']} ({_fmt_price(best['total'])})")
        metrics.append(f"Worst Day: {worst['date']} ({_fmt_price(worst['total'])})")

    insights = ["Key Metrics:"]
    insights.extend(f"• {m}" for m in metrics)
    add_bullets(slide2, insights, top=Inches(1.2))

    # --- Slide 3: Daily Sales Trend ---
    slide3 = prs.slides.add_slide(blank_layout)
    add_title(slide3, "Daily Sales Trend")

    if daily_trend:
        fig, ax = plt.subplots(figsize=(8, 3.5))
        dates = [d["date"] for d in daily_trend]
        totals = [d["total"] / 100 for d in daily_trend]
        ax.plot(dates, totals, marker='o', color='#2196F3', linewidth=2)
        ax.fill_between(range(len(totals)), totals, alpha=0.15, color='#2196F3')
        ax.set_ylabel("Revenue (₹)")
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        chart_path = str(OUTPUT_DIR / "_chart_daily_sales.png")
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        slide3.shapes.add_picture(chart_path, Inches(0.5), Inches(1.2), width=Inches(9))
    else:
        add_bullets(slide3, ["Limited data — no daily sales to chart."], top=Inches(1.5))

    # --- Slide 4: Top Items by Revenue ---
    slide4 = prs.slides.add_slide(blank_layout)
    add_title(slide4, "Top Items by Revenue")

    if top_items:
        names = [i["product"][:20] for i in top_items[:8]][::-1]
        revenues = [i["revenue"] / 100 for i in top_items[:8]][::-1]
        fig, ax = plt.subplots(figsize=(8, 3.5))
        colors = plt.cm.Blues([0.4 + 0.6 * i / len(revenues) for i in range(len(revenues))])
        ax.barh(names, revenues, color=colors)
        ax.set_xlabel("Revenue (₹)")
        plt.tight_layout()
        chart_path = str(OUTPUT_DIR / "_chart_top_items.png")
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        slide4.shapes.add_picture(chart_path, Inches(0.5), Inches(1.2), width=Inches(9))

        if top_items:
            add_bullets(slide4, [f"Top item: {top_items[0]['product']} ({_fmt_price(top_items[0]['revenue'])})"], top=Inches(5.3))
    else:
        add_bullets(slide4, ["No item data available for this period."], top=Inches(1.5))

    # --- Slide 5: Payment Mode Distribution ---
    slide5 = prs.slides.add_slide(blank_layout)
    add_title(slide5, "Payment Mode Distribution")

    if payment_dist:
        labels = list(payment_dist.keys())
        sizes = [payment_dist[k] for k in labels]
        fig, ax = plt.subplots(figsize=(6, 4))
        colors_pie = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0']
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.0f%%',
            colors=colors_pie[:len(labels)], startangle=90,
            textprops={'fontsize': 10}
        )
        ax.axis('equal')
        plt.tight_layout()
        chart_path = str(OUTPUT_DIR / "_chart_payment.png")
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        slide5.shapes.add_picture(chart_path, Inches(2), Inches(1.2), width=Inches(6))

        top_mode = max(payment_dist, key=payment_dist.get)
        add_bullets(slide5, [f"{top_mode} dominates at {payment_dist[top_mode] * 100 // sum(payment_dist.values())}% of payments."], top=Inches(5.3))
    else:
        add_bullets(slide5, ["No payment data available."], top=Inches(1.5))

    # --- Slide 6: GST Collected by Slab ---
    slide6 = prs.slides.add_slide(blank_layout)
    add_title(slide6, "GST Collected by Slab")

    if gst_by_slab:
        slabs = [f"{g['gst_slab']}%" for g in gst_by_slab]
        gst_vals = [g["gst_collected"] / 100 for g in gst_by_slab]
        fig, ax = plt.subplots(figsize=(7, 3.5))
        bars = ax.bar(slabs, gst_vals, color=['#66BB6A', '#42A5F5', '#AB47BC', '#EF5350'])
        ax.set_ylabel("Tax Collected (₹)")
        for bar, val in zip(bars, gst_vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"₹{val:.0f}", ha='center', fontsize=10)
        plt.tight_layout()
        chart_path = str(OUTPUT_DIR / "_chart_gst.png")
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        slide6.shapes.add_picture(chart_path, Inches(1), Inches(1.2), width=Inches(7))

        max_slab = max(gst_by_slab, key=lambda g: g["gst_collected"])
        add_bullets(slide6, [f"{max_slab['gst_slab']}% slab contributes the most GST ({_fmt_price(max_slab['gst_collected'])})."], top=Inches(5.3))
    else:
        add_bullets(slide6, ["No GST data available."], top=Inches(1.5))

    # --- Slide 7: Stock Health ---
    slide7 = prs.slides.add_slide(blank_layout)
    add_title(slide7, "Stock Health")

    low_items = [i for i in inv_items if i["quantity"] <= i.get("reorder_level", 5)]
    healthy_items = [i for i in inv_items if i["quantity"] > i.get("reorder_level", 5)]

    if low_items or healthy_items:
        all_items = healthy_items + low_items
        names_health = [f"{i['name'][:15]} ({i['quantity']:.0f})" for i in all_items][::-1]
        qty_health = [i["quantity"] for i in all_items][::-1]
        colors_health = ["#4CAF50"] * len(healthy_items) + ["#F44336"] * len(low_items)
        colors_health = colors_health[-len(names_health):]

        fig, ax = plt.subplots(figsize=(8, max(3, len(names_health) * 0.4)))
        ax.barh(names_health, qty_health, color=colors_health[:len(names_health)])
        ax.set_xlabel("Quantity")
        plt.tight_layout()
        chart_path = str(OUTPUT_DIR / "_chart_stock_health.png")
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        slide7.shapes.add_picture(chart_path, Inches(0.5), Inches(1.2), width=Inches(9))

        low_names = [i["name"] for i in low_items[:5]]
        low_msg = f"Items needing restock: {', '.join(low_names)}." if low_names else "Stock levels healthy."
        add_bullets(slide7, [low_msg, f"Inventory value (cost): {_fmt_price(inventory.get('total_cost_value', 0))}"], top=Inches(5.3))
    else:
        add_bullets(slide7, ["No stock data available."], top=Inches(1.5))

    file_path = OUTPUT_DIR / f"analysis_{today.isoformat()}.pptx"
    prs.save(str(file_path))

    return {
        "file_path": str(file_path),
        "period": period,
        "message": f"Analysis deck ready for {start} to {end}.",
    }
