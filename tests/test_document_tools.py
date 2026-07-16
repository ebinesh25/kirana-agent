"""Tests for document generation tools (PDF invoice + PPTX analysis deck).

Tests call tools directly (not through the agent loop).
Uses test DB fixtures: create_all + seed per test.

PDF content verification uses pdfplumber for text extraction.
PPTX verification uses python-pptx to inspect slide count and shapes.
"""

from pathlib import Path

import pdfplumber

from kirana.tools.billing import create_bill, add_item, finalize_bill
from kirana.tools.memory import set_preference
from kirana.tools.documents import generate_invoice_pdf, generate_analysis_pptx
from kirana.config import settings

OUTPUT_DIR = Path(settings.OUTPUT_DIR)


def _pdf_text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


# ---------------------------------------------------------------------------
# PDF Invoice tests
# ---------------------------------------------------------------------------

class TestGenerateInvoicePdf:
    def _create_finalized_bill(self, customer_name=None):
        """Helper: create a bill, add Maggi + Sugar, finalize."""
        b = create_bill(customer_name=customer_name)["bill"]
        add_item(b["id"], product_id=5, quantity=2)  # Maggi, ₹14, 12%
        add_item(b["id"], product_id=8, quantity=1)  # Sugar loose, ₹45/kg, 5%
        result = finalize_bill(b["id"], payment_mode="upi", payment_ref="UTR123")
        return result["bill"]

    def test_generate_invoice_pdf_finalized_bill(self):
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        assert "error" not in result
        assert "file_path" in result
        path = Path(result["file_path"])
        assert path.exists()
        assert path.stat().st_size > 0
        assert result["bill_number"] == bill["bill_number"]

    def test_generate_invoice_pdf_draft_bill_rejected(self):
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=2)
        result = generate_invoice_pdf(b["id"])
        assert "error" in result
        assert "draft" in result["error"].lower()

    def test_generate_invoice_pdf_includes_shop_name(self):
        set_preference("shop_name", "Test Kirana Shop")
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        assert "Test Kirana Shop" in text

    def test_generate_invoice_pdf_includes_gstin(self):
        set_preference("gstin", "27AABCU1234D1Z1")
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        assert "27AABCU1234D1Z1" in text

    def test_generate_invoice_pdf_includes_tax_breakup(self):
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        assert "CGST" in text
        assert "SGST" in text
        assert "Total Tax" in text

    def test_generate_invoice_pdf_includes_hsn_codes(self):
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        assert "1902" in text or "1701" in text

    def test_generate_invoice_pdf_correct_grand_total(self):
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        expected = f"\u20b9{bill['grand_total'] // 100}.{bill['grand_total'] % 100:02d}"
        assert expected in text

    def test_generate_invoice_pdf_default_shop_name(self):
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        assert "Kirana Store" in text

    def test_generate_invoice_pdf_payment_details(self):
        bill = self._create_finalized_bill()
        result = generate_invoice_pdf(bill["id"])
        text = _pdf_text(result["file_path"])
        assert "upi" in text.lower() or "UPI" in text


# ---------------------------------------------------------------------------
# PPTX Analysis Deck tests
# ---------------------------------------------------------------------------

class TestGenerateAnalysisPptx:
    def _seed_sales_data(self):
        """Create 2 finalized bills to have some analysis data."""
        b1 = create_bill()["bill"]
        add_item(b1["id"], product_id=5, quantity=3)
        finalize_bill(b1["id"], payment_mode="upi", payment_ref="UPI1")

        b2 = create_bill()["bill"]
        add_item(b2["id"], product_id=3, quantity=2)
        add_item(b2["id"], product_id=8, quantity=1)
        finalize_bill(b2["id"], payment_mode="cash")

    def test_generate_analysis_pptx_with_data(self):
        self._seed_sales_data()
        result = generate_analysis_pptx(period="week")
        assert "error" not in result
        assert "file_path" in result
        path = Path(result["file_path"])
        assert path.exists()
        assert path.stat().st_size > 0

    def test_generate_analysis_pptx_sparse_data(self):
        """1 day of sales → still generates."""
        b = create_bill()["bill"]
        add_item(b["id"], product_id=5, quantity=1)
        finalize_bill(b["id"], payment_mode="cash")
        result = generate_analysis_pptx(period="week")
        assert "error" not in result
        assert Path(result["file_path"]).exists()

    def test_generate_analysis_pptx_no_data(self):
        """0 sales → generates with fallback content."""
        result = generate_analysis_pptx(period="week")
        assert "error" not in result
        assert Path(result["file_path"]).exists()

    def test_generate_analysis_pptx_has_multiple_slides(self):
        self._seed_sales_data()
        result = generate_analysis_pptx(period="week")
        from pptx import Presentation
        prs = Presentation(str(result["file_path"]))
        assert len(prs.slides) >= 5

    def test_generate_analysis_pptx_charts_embedded(self):
        self._seed_sales_data()
        result = generate_analysis_pptx(period="week")
        from pptx import Presentation
        prs = Presentation(str(result["file_path"]))
        pic_count = sum(
            1 for slide in prs.slides
            for shape in slide.shapes
            if shape.shape_type == 13
        )
        assert pic_count >= 3

    def test_generate_analysis_pptx_custom_period(self):
        self._seed_sales_data()
        result = generate_analysis_pptx(period="month")
        assert "error" not in result
        assert Path(result["file_path"]).exists()

    def test_generate_analysis_pptx_invalid_period_rejected(self):
        result = generate_analysis_pptx(period="invalid")
        assert "error" in result
