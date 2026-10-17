import pandas as pd
from app import tools


def test_vendor_cost_above_selling_price_is_loss_risk(monkeypatch):
    frames = {
        "products.csv": pd.DataFrame([
            {"sku": "SMALL-LOSS", "product": "Example A", "price": 525},
            {"sku": "BREAK-EVEN", "product": "Example B", "price": 549},
            {"sku": "PROFIT", "product": "Example C", "price": 600},
        ]),
        "vendor_prices.csv": pd.DataFrame([
            {"sku": "SMALL-LOSS", "vendor": "Vendor A", "price": 549},
            {"sku": "BREAK-EVEN", "vendor": "Vendor B", "price": 549},
            {"sku": "PROFIT", "vendor": "Vendor C", "price": 500},
        ]),
    }
    monkeypatch.setattr(tools, "read_csv", lambda name: frames[name].copy())
    result = tools.price_validation()
    rows = {r["sku"]: r for r in result["rows"]}
    assert bool(rows["SMALL-LOSS"]["exception"])
    assert rows["SMALL-LOSS"]["vendor_cost_minus_selling_price"] == 24
    assert "LOSS RISK" in rows["SMALL-LOSS"]["validation_status"]
    assert not bool(rows["BREAK-EVEN"]["exception"])
    assert rows["BREAK-EVEN"]["validation_status"].startswith("OK")
    assert not bool(rows["PROFIT"]["exception"])


def test_one_rupee_loss_is_flagged(monkeypatch):
    frames = {
        "products.csv": pd.DataFrame([{"sku": "SKU-1", "product": "Test", "price": 525}]),
        "vendor_prices.csv": pd.DataFrame([{"sku": "SKU-1", "vendor": "Vendor", "price": 526}]),
    }
    monkeypatch.setattr(tools, "read_csv", lambda name: frames[name].copy())
    row = tools.price_validation()["rows"][0]
    assert bool(row["exception"])
    assert row["vendor_cost_minus_selling_price"] == 1
    assert "LOSS RISK" in row["validation_status"]
