from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict
import re
import pandas as pd
import numpy as np
from app.llm import generate_text, classify_keywords
from app.config import SLOW_STEP_THRESHOLD_SECONDS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def read_csv(name):
    path = DATA / name
    if not path.exists():
        raise FileNotFoundError(f"Required sample data file is missing: {path.name}")
    return pd.read_csv(path)

def _norm(value):
    return " ".join(str(value).strip().lower().split())

def inventory_restock():
    df = read_csv("inventory.csv")
    required = {"product", "current_stock", "minimum_stock"}
    if not required.issubset(df.columns):
        raise ValueError(f"inventory.csv must contain {sorted(required)}")
    df["current_stock"] = pd.to_numeric(df["current_stock"], errors="coerce")
    df["minimum_stock"] = pd.to_numeric(df["minimum_stock"], errors="coerce")
    bad = df[["current_stock", "minimum_stock"]].isna().any(axis=1)
    if bad.any():
        raise ValueError(f"Invalid stock values in rows: {(df.index[bad]+2).tolist()}")
    low = df[df.current_stock < df.minimum_stock].copy()
    low["suggested_reorder_quantity"] = low["minimum_stock"] * 2 - low["current_stock"]
    return {"restock_products": low.to_dict("records"), "count": int(len(low))}

def price_validation():
    products, vendors = read_csv("products.csv"), read_csv("vendor_prices.csv")
    for df, name in [(products, "products.csv"), (vendors, "vendor_prices.csv")]:
        if not {"sku", "price"}.issubset(df.columns):
            raise ValueError(f"{name} must contain sku and price")
    products = products.copy()
    vendors = vendors.copy()
    products["sku"] = products["sku"].fillna("").astype(str).str.strip().str.upper()
    vendors["sku"] = vendors["sku"].fillna("").astype(str).str.strip().str.upper()
    products["price"] = pd.to_numeric(products["price"], errors="coerce")
    vendors["price"] = pd.to_numeric(vendors["price"], errors="coerce")
    merged = products.merge(vendors, on="sku", how="left", suffixes=("_internal", "_vendor"), indicator=True)
    valid_prices = (merged["price_internal"].notna() & merged["price_vendor"].notna() &
                    (merged["price_internal"] > 0) & (merged["price_vendor"] >= 0))
    # Any vendor cost above selling price is a loss risk, regardless of percentage.
    merged["vendor_cost_minus_selling_price"] = np.where(
        valid_prices, merged["price_vendor"] - merged["price_internal"], np.nan
    )
    merged["loss_risk"] = valid_prices & (merged["price_vendor"] > merged["price_internal"])
    merged["percentage_difference"] = np.where(
        valid_prices,
        (merged["price_vendor"] - merged["price_internal"]) / merged["price_internal"].abs() * 100,
        np.nan
    )
    invalid_price = ~valid_prices
    merged["exception"] = (merged["_merge"] != "both") | invalid_price | merged["loss_risk"]
    merged["validation_status"] = np.where(
        merged["_merge"] != "both", "Vendor price missing",
        np.where(invalid_price, "Invalid or missing price",
        np.where(merged["loss_risk"],
            "LOSS RISK: vendor cost exceeds selling price by " +
            merged["vendor_cost_minus_selling_price"].fillna(0).map(lambda x: f"{x:.2f}"),
            "OK: selling price covers vendor cost"))
    )
    return {"rows": merged.replace({np.nan: None}).to_dict("records"),
            "exceptions": merged[merged.exception].replace({np.nan: None}).to_dict("records"),
            "exception_count": int(merged.exception.sum())}

def process_vendor_file(uploaded_file=None, file_path=None):
    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(uploaded_file)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError("Upload a CSV or Excel (.xlsx/.xls) vendor file.")
    elif file_path:
        p = Path(file_path)
        df = pd.read_csv(p) if p.suffix.lower() == ".csv" else pd.read_excel(p)
    else:
        df = read_csv("vendor_upload_sample.csv")
    original_columns = list(df.columns)
    # Normalize common vendor aliases without guessing values.
    def normalize_column(value):
        key = _norm(value).replace("-", " ").replace("_", " ")
        key = " ".join(key.split())
        aliases = {
            "sku": {"sku", "sku id", "product sku", "item sku", "item code", "product code", "vendor sku"},
            "product_name": {"product name", "product", "name", "item name", "title", "product title"},
            "price": {"price", "unit price", "vendor price", "cost"},
            "category": {"category", "product category", "type"},
            "brand": {"brand", "manufacturer"},
        }
        for canonical, choices in aliases.items():
            if key in choices:
                return canonical
        return key.replace(" ", "_")
    df.columns = [normalize_column(c) for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError(f"Column normalization created duplicate columns. Original columns: {original_columns}")
    required = ["sku", "product_name"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found after alias detection. Original columns: {original_columns}")
    invalid_mask = df["sku"].isna() | df["product_name"].isna() | (df["sku"].astype(str).str.strip() == "") | (df["product_name"].astype(str).str.strip() == "")
    invalid = df[invalid_mask].copy()
    cleaned = df[~invalid_mask].copy()
    return {"cleaned_rows": cleaned.to_dict("records"), "invalid_rows": invalid.to_dict("records"),
            "cleaned_count": int(len(cleaned)), "invalid_count": int(len(invalid)),
            "normalized_columns": list(df.columns)}

def product_description(user_request):
    # Detect absent fields explicitly and pass the list to the LLM so missing facts
    # are surfaced in the output rather than filled in from assumptions.
    low = user_request.lower()
    known_fields = {
        "product name": ("product:", "product name:", "name:"),
        "category": ("category:",),
        "attributes": ("attributes:", "features:"),
        "material": ("material:",),
        "color": ("color:", "colour:"),
        "target audience": ("audience:", "target audience:"),
    }
    missing = [label for label, markers in known_fields.items() if not any(marker in low for marker in markers)]
    prompt = f"""
Create product SEO content using only the attributes actually supplied by the user.
Never invent missing attributes. Clearly mark unavailable details as "Not provided".
Explicitly list these missing fields: {missing}.
Return headings: Product Description, Short Description, SEO Title, Meta Description, Missing Information.
User request: {user_request}
"""
    content = generate_text(prompt)
    return {"content": content, "missing_attributes": missing,
            "validation_note": "Missing attributes must remain marked Not provided; do not infer product facts."}

def order_status(user_request):
    df = read_csv("orders.csv")
    request = user_request.lower()
    matched = df[df["order_id"].astype(str).str.lower().apply(lambda x: x in request)]
    if matched.empty:
        matched = df[df["customer_email"].astype(str).str.lower().apply(lambda x: x in request)]
    if matched.empty:
        return {"found": False, "message": "No order found. Please provide a valid order ID or customer email."}
    return {"found": True, "orders": matched.to_dict("records")}

def duplicate_detection():
    df = read_csv("product_catalog.csv")
    required = {"sku", "product_name", "category", "brand"}
    if not required.issubset(df.columns):
        raise ValueError(f"product_catalog.csv must contain {sorted(required)}")
    groups, used = [], set()
    rows = df.to_dict("records")
    for i, a in enumerate(rows):
        if i in used: continue
        matches = []
        for j in range(i+1, len(rows)):
            if j in used: continue
            b = rows[j]
            sku_a, sku_b = _norm(a["sku"]), _norm(b["sku"])
            if sku_a and sku_b and sku_a == sku_b:
                confidence, reason = 1.0, "Exact SKU match"
            else:
                name_sim = SequenceMatcher(None, _norm(a["product_name"]), _norm(b["product_name"])).ratio()
                attr_sim = sum(_norm(a[k]) == _norm(b[k]) for k in ("category", "brand")) / 2
                confidence = 0.7 * name_sim + 0.3 * attr_sim
                reason = "Name/category/brand similarity"
            if confidence >= 0.82:
                matches.append({"product": b, "confidence": round(confidence, 3), "reason": reason})
                used.add(j)
        if matches:
            used.add(i)
            groups.append({"primary_product": a, "matches": matches})
    return {"duplicate_groups": groups, "group_count": len(groups)}

def campaign_brief(user_request):
    low = user_request.lower()
    missing = []
    if not any(x in low for x in ("goal", "launch", "awareness", "sales", "promote", "conversion", "collection")):
        missing.append("campaign goal")
    if not any(x in low for x in ("202", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "date")):
        missing.append("campaign dates")
    if missing:
        return {"needs_input": True, "missing_inputs": missing,
                "message": "Please provide " + " and ".join(missing) + " before generating the campaign brief."}
    prompt = f"""
Create a structured marketing campaign brief. Include objective, audience, product summary,
core messaging, channel recommendations, timeline, and execution checklist. Do not invent
specific product facts that are not provided. User request: {user_request}
"""
    return {"needs_input": False, "brief": generate_text(prompt)}

def seo_keyword_classification(user_request):
    # Accept comma/newline-separated keywords after a colon, or use sample keywords.
    if ":" in user_request:
        raw = user_request.split(":", 1)[1]
        keywords = [x.strip() for x in raw.replace("\\n", ",").split(",") if x.strip()]
    else:
        keywords = read_csv("keywords.csv")["keyword"].dropna().astype(str).tolist()
    unique, seen = [], set()
    for keyword in keywords:
        key = _norm(keyword)
        if key and key not in seen:
            unique.append(keyword.strip())
            seen.add(key)
    context = user_request.split(":", 1)[0] if ":" in user_request else "general product/category"
    if not unique:
        raise ValueError("No keywords supplied after duplicate removal.")
    classified = classify_keywords(unique, context)
    allowed_intents = {"informational", "commercial", "transactional", "navigational"}
    by_key = {_norm(item.get("keyword", "")): item for item in classified if isinstance(item, dict)}
    missing = [kw for kw in unique if _norm(kw) not in by_key]
    if missing:
        raise ValueError(f"Gemini omitted keyword classifications for: {missing}")
    normalized = []
    for keyword in unique:
        item = dict(by_key[_norm(keyword)])
        intent = _norm(item.get("intent", ""))
        if intent not in allowed_intents:
            raise ValueError(f"Invalid search intent for '{keyword}': {item.get('intent')}")
        item["keyword"], item["intent"] = keyword, intent
        normalized.append(item)
    return {"classifications": normalized, "count": len(normalized), "duplicates_removed": len(keywords) - len(unique)}

def employee_task_assignment(user_request):
    df = read_csv("employees.csv")
    required = {"employee", "skills", "current_workload", "capacity", "availability"}
    if not required.issubset(df.columns):
        raise ValueError(f"employees.csv must contain {sorted(required)}")
    # Extract task skills from common technical terms; generic requests use task words.
    terms = ["python", "sql", "machine learning", "ai", "data", "frontend", "backend", "api", "excel", "testing", "developer"]
    req = {t for t in terms if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", user_request.lower())}
    # A generic "developer" request is a software-development role, not a literal
    # skill named developer; broaden to skills present in the sample employee catalog.
    if "developer" in req:
        req.remove("developer")
        req.update({"python", "backend", "api", "frontend"})
    ranked = []
    for row in df.to_dict("records"):
        skills = _norm(row["skills"])
        skill_matches = sorted(t for t in req if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", skills))
        capacity_left = float(row["capacity"]) - float(row["current_workload"])
        if str(row["availability"]).lower() not in ("yes", "true", "available", "1"):
            continue
        score = (len(skill_matches) * 10) + max(0, capacity_left) - float(row["current_workload"])
        if capacity_left > 0:
            ranked.append({"employee": row["employee"], "skills_matched": skill_matches,
                           "workload": row["current_workload"], "capacity_left": capacity_left,
                           "score": round(score, 2), "employee_record": row})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    if not req and "skill" in user_request.lower():
        return {"assigned": False, "escalation": True,
                "message": "No available employee matches the explicitly requested skills. Escalate to the manager.",
                "required_skills": "Not represented in the supported employee skill catalog", "candidates": ranked}
    if not req:
        return {"assigned": False, "needs_input": True, "escalation": False,
                "message": "Please provide the task description or required skills so candidates can be ranked fairly.",
                "missing_inputs": ["task description or required skills"], "candidates": ranked}
    if not ranked or not any(x["skills_matched"] for x in ranked):
        return {"assigned": False, "escalation": True, "message": "No suitable available employee found. Escalate to the manager.", "candidates": ranked}
    best = ranked[0]
    return {"assigned": True, "recommended_employee": best["employee"],
            "reason": f"Matched skills: {', '.join(best['skills_matched']) or 'general task fit'}; remaining capacity: {best['capacity_left']}.",
            "priority": "Urgent" if "urgent" in user_request.lower() else "Normal",
            "deadline": "Use the deadline provided in the request; not specified" if not any(x in user_request.lower() for x in ("today", "tomorrow", "deadline", "by ")) else "As specified in request",
            "task_summary": user_request, "ranked_candidates": ranked}

def performance_report():
    df = read_csv("workflow_logs.csv")
    required = {"workflow_id", "status", "execution_seconds", "step", "error"}
    if not required.issubset(df.columns):
        raise ValueError(f"workflow_logs.csv must contain {sorted(required)}")
    df["status_normalized"] = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["duration_numeric"] = pd.to_numeric(df["execution_seconds"], errors="coerce")
    df["error_normalized"] = df["error"].fillna("").astype(str).str.strip()
    rows = []
    for wf, group in df.groupby("workflow_id"):
        total = len(group)
        failures = int((group["status_normalized"] != "success").sum())
        rate = failures / total * 100 if total else 0
        durations = group["duration_numeric"].dropna()
        avg = float(durations.mean()) if not durations.empty else 0.0
        errors = group.loc[group["error_normalized"] != "", "error_normalized"].value_counts().to_dict()
        rows.append({"workflow_id": wf, "runs": total, "failures": failures,
                     "failure_rate_percent": round(rate, 2), "average_execution_seconds": round(avg, 2),
                     "frequent_errors": errors, "flag_failure_rate": rate > 10,
                     "flag_slow_average": avg > SLOW_STEP_THRESHOLD_SECONDS})
    rows.sort(key=lambda x: (x["failure_rate_percent"], x["average_execution_seconds"]), reverse=True)
    step_rows = []
    for step, group in df.groupby("step", dropna=False):
        durations = group["duration_numeric"].dropna()
        avg = float(durations.mean()) if not durations.empty else 0.0
        step_rows.append({"step": str(step), "runs": int(len(group)),
                          "average_execution_seconds": round(avg, 2),
                          "flag_slow": avg > SLOW_STEP_THRESHOLD_SECONDS})
    step_rows.sort(key=lambda x: x["average_execution_seconds"], reverse=True)
    total_runs = int(len(df))
    return {"workflows": rows, "slow_steps": step_rows,
            "slow_step_threshold_seconds": SLOW_STEP_THRESHOLD_SECONDS,
            "total_runs": total_runs,
            "success_rate_percent": round((df["status_normalized"] == "success").mean() * 100, 2) if total_runs else 0.0,
            "failure_rate_percent": round((df["status_normalized"] != "success").mean() * 100, 2) if total_runs else 0.0}

