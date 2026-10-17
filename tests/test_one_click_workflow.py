from pathlib import Path
import shutil
import pandas as pd
from app.workflow_loader import create_custom_workflow, delete_custom_workflow, load_workflows
from app.engine import WorkflowEngine

def copied_workbook(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data" / "AI_Agent_Workflow_Assessment.xlsx"
    target = tmp_path / "workflows.xlsx"
    shutil.copy2(source, target)
    return target

def test_create_custom_workflow_appends_wf011_and_loads(tmp_path):
    workbook = copied_workbook(tmp_path)
    created = create_custom_workflow("Delivery Policy Helper", "User asks about delivery policy", "Question", "delivery, shipping", "Read request → Return answer", "Return configured answer", "Delivery usually takes 3-5 business days.", path=workbook)
    assert created["Workflow_ID"] == "WF011"
    workflows = load_workflows(workbook)
    custom = next(w for w in workflows if w["Workflow_ID"] == "WF011")
    assert custom["Tools_Required"] == "custom_response"
    assert custom["Expected_Output"] == "Delivery usually takes 3-5 business days."

def test_custom_workflow_executes_without_new_python_tool(tmp_path):
    workbook = copied_workbook(tmp_path)
    create_custom_workflow("Delivery Policy Helper", "delivery policy", "Question", "delivery", "Read → Respond", "Always answer", "Delivery takes 3-5 days.", path=workbook)
    engine = WorkflowEngine(workbook=workbook)
    result = engine.run("delivery policy", workflow_override="WF011")
    assert result["selected_workflow"]["id"] == "WF011"
    assert result["result"]["message"] == "Delivery takes 3-5 days."

def test_delete_custom_workflow_only(tmp_path):
    workbook = copied_workbook(tmp_path)
    create_custom_workflow("Delivery Policy Helper", "delivery policy", "Question", "delivery", "Read → Respond", "Always answer", "Delivery takes 3-5 days.", path=workbook)
    assert delete_custom_workflow("WF011", path=workbook) is True
    assert all(w["Workflow_ID"] != "WF011" for w in load_workflows(workbook))
