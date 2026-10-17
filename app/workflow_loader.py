from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx"

REQUIRED_COLUMNS = [
    "Workflow_ID", "Workflow_Name", "Trigger", "Inputs", "Steps",
    "Decision_Logic", "Tools_Required", "Expected_Output"
]

def load_workflows(path=DEFAULT_WORKBOOK):
    path = Path(path) if path is not None else DEFAULT_WORKBOOK
    if not path.exists():
        raise FileNotFoundError(f"Workflow workbook not found: {path}")
    df = pd.read_excel(path, sheet_name="Workflows").fillna("")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Workbook is missing required columns: {missing}")
    workflows = []
    for row in df.to_dict(orient="records"):
        workflows.append({k: str(v).strip() for k, v in row.items()})
    if not workflows:
        raise ValueError("No workflows found in the Workflows sheet.")
    return workflows

def load_test_questions(path=DEFAULT_WORKBOOK):
    df = pd.read_excel(path, sheet_name="Test_Questions").fillna("")
    return df.to_dict(orient="records")


def create_custom_workflow(name, trigger, inputs, keywords, steps, decision_logic, expected_output, path=DEFAULT_WORKBOOK):
    """Append a no-code custom-response workflow to the Workflows sheet."""
    from openpyxl import load_workbook
    path = Path(path)
    if not name.strip() or not trigger.strip() or not expected_output.strip():
        raise ValueError("Workflow name, trigger, and response/output are required.")
    wb = load_workbook(path)
    if "Workflows" not in wb.sheetnames:
        raise ValueError("Workbook is missing the Workflows sheet.")
    ws = wb["Workflows"]
    headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise ValueError(f"Workbook is missing required columns: {missing}")
    id_index = headers.index("Workflow_ID") + 1
    used = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        val = row[id_index - 1] if len(row) >= id_index else None
        match = re.fullmatch(r"WF(\d+)", str(val or "").strip(), re.I)
        if match:
            used.append(int(match.group(1)))
    new_id = f"WF{max(used, default=0) + 1:03d}"
    values = {
        "Workflow_ID": new_id,
        "Workflow_Name": name.strip(),
        "Trigger": (trigger.strip() + (f" Keywords: {keywords.strip()}" if keywords.strip() else "")),
        "Inputs": inputs.strip() or "User request",
        "Steps": steps.strip() or "Read request → Return configured response",
        "Decision_Logic": decision_logic.strip() or "Return the configured response for this custom workflow.",
        "Tools_Required": "custom_response",
        "Expected_Output": expected_output.strip(),
    }
    ws.append([values.get(header, "") for header in headers])
    wb.save(path)
    return values


def delete_custom_workflow(workflow_id, path=DEFAULT_WORKBOOK):
    """Delete only custom-response workflows (never built-in WF001-WF010)."""
    from openpyxl import load_workbook
    path = Path(path)
    wb = load_workbook(path)
    ws = wb["Workflows"]
    headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
    if "Workflow_ID" not in headers or "Tools_Required" not in headers:
        raise ValueError("Workbook is missing required workflow columns.")
    id_col = headers.index("Workflow_ID") + 1
    tool_col = headers.index("Tools_Required") + 1
    for row_num in range(2, ws.max_row + 1):
        current_id = str(ws.cell(row_num, id_col).value or "").strip()
        tool = str(ws.cell(row_num, tool_col).value or "").strip().lower()
        if current_id == workflow_id:
            if tool != "custom_response" or current_id in {f"WF{i:03d}" for i in range(1, 11)}:
                raise ValueError("Only custom workflows can be deleted here.")
            ws.delete_rows(row_num, 1)
            wb.save(path)
            return True
    raise ValueError(f"Custom workflow not found: {workflow_id}")
