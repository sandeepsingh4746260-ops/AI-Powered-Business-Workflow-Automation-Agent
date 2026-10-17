from pathlib import Path
import pandas as pd
from app.workflow_loader import load_workflows, load_test_questions
from app.engine import WorkflowEngine
from app import tools

def test_excel_has_all_ten_workflows():
    workflows = load_workflows()
    assert len(workflows) == 10
    assert {w["Workflow_ID"] for w in workflows} == {f"WF{i:03d}" for i in range(1, 11)}

def test_assignment_test_questions_loaded():
    assert len(load_test_questions()) == 10

def test_inventory_restock_threshold():
    result = tools.inventory_restock()
    assert result["count"] >= 1
    assert all(x["current_stock"] < x["minimum_stock"] for x in result["restock_products"])

def test_price_validation_flags_over_ten_percent():
    result = tools.price_validation()
    assert "exceptions" in result
    assert result["exception_count"] >= 1

def test_vendor_file_validation():
    result = tools.process_vendor_file()
    assert result["invalid_count"] >= 1
    assert result["cleaned_count"] >= 1

def test_order_found_and_not_found():
    found = tools.order_status("Where is order ORD-1001?")
    missing = tools.order_status("Where is order ORD-9999?")
    assert found["found"] is True
    assert missing["found"] is False

def test_duplicate_detection_returns_structure():
    result = tools.duplicate_detection()
    assert "duplicate_groups" in result

def test_campaign_missing_fields_condition():
    result = tools.campaign_brief("Create a campaign brief")
    assert result["needs_input"] is True
    assert "campaign goal" in result["missing_inputs"]
    assert "campaign dates" in result["missing_inputs"]

def test_employee_assignment_returns_decision():
    result = tools.employee_task_assignment("Assign an urgent Python API developer task by tomorrow")
    assert "assigned" in result

def test_performance_report_flags_failure_rate():
    result = tools.performance_report()
    assert result["total_runs"] > 0
    assert "workflows" in result
    assert any("flag_failure_rate" in w for w in result["workflows"])

def test_manual_override_selects_expected_workflow_without_api():
    engine = WorkflowEngine()
    result = engine.run("which products need restocking", workflow_override="WF001")
    assert result["selected_workflow"]["id"] == "WF001"
    assert "result" in result

def test_unknown_manual_override_is_handled():
    engine = WorkflowEngine()
    result = engine.run("test", workflow_override="WF999")
    assert "error" in result
