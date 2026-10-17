"""Contract-style end-to-end tests for every assignment test request (Gemini mocked)."""
import pandas as pd
from app import tools
from app.engine import WorkflowEngine, _step_list
from app.workflow_loader import load_test_questions


def test_all_assignment_prompts_route_to_expected_workflow_and_execute(monkeypatch):
    questions = load_test_questions()
    prompt_to_id = {str(row["Test_Request"]): str(row["Workflow_ID"]) for row in questions}
    monkeypatch.setattr("app.engine.choose_workflow", lambda request, workflows: {
        "workflow_id": prompt_to_id[request], "reason": "Mocked Gemini route contract", "missing_inputs": []
    })
    monkeypatch.setattr(tools, "generate_text", lambda prompt: (
        "Product Description: Not provided\nShort Description: Not provided\nSEO Title: Product\nMeta Description: Not provided"
    ))
    monkeypatch.setattr(tools, "classify_keywords", lambda keywords, context: [
        {"keyword": kw, "intent": "commercial", "category": context, "priority": "Medium",
         "recommended_target_page": "/category"} for kw in keywords
    ])
    engine = WorkflowEngine()
    for question in questions:
        request = str(question["Test_Request"])
        expected = str(question["Workflow_ID"])
        result = engine.run(request, uploaded_file=None)
        assert result.get("selected_workflow", {}).get("id") == expected, (request, result)
        assert "steps" in result and result["steps"], request
        assert "result" in result or "error" in result, request


def test_excel_steps_are_used_in_execution_trace():
    engine = WorkflowEngine()
    workflow = next(w for w in engine.workflows if w["Workflow_ID"] == "WF001")
    result = engine.run("Which products need restocking?", workflow_override="WF001")
    traced = [s for s in result["steps"] if s["step"].split(". ", 1)[0].isdigit()]
    assert len(traced) == len(_step_list(workflow))
    assert all(s["status"] == "completed" for s in traced)


def test_vendor_column_aliases_and_missing_values_are_handled(monkeypatch, tmp_path):
    source = tmp_path / "vendor.csv"
    source.write_text("SKU ID,Product Name,Unit Price\nA-1,Water Bottle,10\n,Missing SKU,12\nA-3,,15\n", encoding="utf-8")
    result = tools.process_vendor_file(file_path=source)
    assert result["cleaned_count"] == 1
    assert result["invalid_count"] == 2
    assert {"sku", "product_name", "price"}.issubset(result["normalized_columns"])


def test_keyword_duplicates_are_removed_before_classification(monkeypatch):
    captured = {}
    def fake_classify(keywords, context):
        captured["keywords"] = keywords
        return [{"keyword": kw, "intent": "informational", "category": context,
                 "priority": "Low", "recommended_target_page": "/guide"} for kw in keywords]
    monkeypatch.setattr(tools, "classify_keywords", fake_classify)
    result = tools.seo_keyword_classification("Classify keywords: running shoes, Running Shoes, buy shoes")
    assert captured["keywords"] == ["running shoes", "buy shoes"]
    assert result["duplicates_removed"] == 1


def test_employee_assignment_does_not_assign_without_skill_match(monkeypatch):
    result = tools.employee_task_assignment("Assign task to someone with quantum welding skills")
    assert result["assigned"] is False
    assert result["escalation"] is True


def test_performance_report_includes_slow_steps_and_configurable_threshold(monkeypatch):
    monkeypatch.setattr(tools, "SLOW_STEP_THRESHOLD_SECONDS", 4.0)
    result = tools.performance_report()
    assert "slow_steps" in result
    assert result["slow_step_threshold_seconds"] == 4.0
    assert all("flag_slow" in item for item in result["slow_steps"])


def test_price_validation_normalizes_skus_and_flags_invalid_prices(monkeypatch):
    import pandas as pd
    frames = {
        "products.csv": pd.DataFrame([{"sku": " ab-1 ", "price": 100}, {"sku": "ZERO", "price": 0}]),
        "vendor_prices.csv": pd.DataFrame([{"sku": "AB-1", "price": 115}, {"sku": "ZERO", "price": 12}]),
    }
    monkeypatch.setattr(tools, "read_csv", lambda name: frames[name].copy())
    result = tools.price_validation()
    assert result["exception_count"] == 2
    assert result["rows"][0]["percentage_difference"] == 15.0
    assert result["rows"][1]["validation_status"] == "Invalid or missing price"
