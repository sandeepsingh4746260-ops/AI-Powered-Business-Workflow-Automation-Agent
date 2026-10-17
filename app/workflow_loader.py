from pathlib import Path
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
