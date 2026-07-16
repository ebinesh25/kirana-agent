"""Read-only SQL query tool for ad-hoc reporting and listing.

Lets the agent answer any "list/show/find" question without a custom tool.
All mutations must use the dedicated tools (billing, khata, inventory, etc.).
"""

import re
from sqlalchemy import text
from kirana.db.connection import engine

BLOCKED_TABLES = ("processed_updates", "chat_state")
BLOCKED_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "TRUNCATE", "CREATE", "EXECUTE", "REPLACE", "GRANT",
)


def _is_safe_select(query: str) -> tuple[bool, str]:
    stripped = query.strip()

    # Must start with SELECT
    if not stripped.upper().startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    # Reject blocked keywords (case-insensitive, whole-word match)
    upper = stripped.upper()
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper):
            return False, f"Keyword '{kw}' is not allowed. Read-only queries only."

    # Reject queries targeting internal tables
    for tbl in BLOCKED_TABLES:
        if re.search(rf"\b{tbl}\b", stripped.lower()):
            return False, f"Table '{tbl}' is internal and cannot be queried."

    return True, ""


def run_sql_query(query: str) -> dict:
    """Run a read-only SQL query on the store database.

    Only SELECT statements are accepted. Useful for ad-hoc listing,
    reporting, and finding records when a dedicated tool doesn't exist.

    Args:
        query: A SELECT SQL statement
    """
    safe, reason = _is_safe_select(query)
    if not safe:
        return {"error": reason}

    # Auto-append LIMIT if missing
    upper = query.strip().upper()
    if "LIMIT" not in upper:
        query = query.rstrip("; \t\r\n") + " LIMIT 200"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        return {
            "error": f"Query failed: {e}",
            "query": query,
        }

    # Format prices if paise columns detected
    for row in rows:
        for col in ("grand_total", "total_spent", "amount", "balance",
                     "sell_price", "cost_price", "mrp", "subtotal",
                     "total_cgst", "total_sgst", "total_tax", "round_off",
                     "line_total", "cgst_amount", "sgst_amount"):
            if col in row and isinstance(row[col], int):
                row[f"{col}_fmt"] = f"\u20b9{row[col] // 100}.{row[col] % 100:02d}"

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "message": f"Query returned {len(rows)} row(s)." if rows else "Query returned no rows.",
    }
