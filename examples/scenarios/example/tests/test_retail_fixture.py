"""Cross-check the committed SQL migrations, CSV fixture and MCP contract."""
import csv
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data"


def test_retail_fixture_matches_flyway_seed_and_exact_business_totals():
    rows = list(csv.DictReader((BASE / "sales.csv").open()))
    assert len(rows) == 196
    assert {int(r["product_id"]) for r in rows} <= set(range(1, 13))
    assert {int(r["store_id"]) for r in rows} == {1, 2, 3}
    days = {date.fromisoformat(r["sold_at"]) for r in rows}
    assert days == {date(2026, 10, 26) + timedelta(days=i) for i in range(28)}
    sql = (BASE / "V2__seed_demo_sales.sql").read_text()
    # The migration contains the same row tuples in the INSERT sales section.
    match = re.search(r"INSERT INTO sales .*? VALUES\s*(.*?);", sql, re.S)
    assert match
    sql_sales = re.findall(r"\((\d+),(\d+),(\d+),'(\d{4}-\d{2}-\d{2})',(\d+),(\d+)\)", match.group(1))
    csv_sales = [tuple(r[k] for k in ("id", "product_id", "store_id", "sold_at", "quantity", "unit_price_cents")) for r in rows]
    assert sql_sales == csv_sales

    def summary(a, b):
        filtered = [r for r in rows if a <= r["sold_at"] <= b]
        return len(filtered), sum(int(r["quantity"]) for r in filtered), sum(
            int(r["quantity"]) * int(r["unit_price_cents"]) for r in filtered
        )

    assert summary("2026-11-09", "2026-11-15") == (49, 160, 86460)
    assert summary("2026-11-16", "2026-11-22") == (49, 169, 91641)


def test_rest_to_mcp_operations_follow_spec_01_contract():
    doc = json.loads((BASE / "retail-operations.json").read_text())
    ops = {x["name"]: x for x in doc["operations"]}
    assert set(ops) == {"sales_summary", "top_products", "sales_by_category", "compare_sales_periods"}
    assert all(x["method"] == "GET" and x["path"].startswith("/api/insights/") for x in ops.values())
    assert set(ops["sales_summary"]["parameters"]) == {"from", "to"}
    assert set(ops["compare_sales_periods"]["parameters"]) == {"from", "to", "previousFrom", "previousTo"}
