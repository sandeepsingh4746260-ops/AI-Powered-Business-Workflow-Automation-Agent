"""Excel-driven workflow orchestrator. Business execution stays in typed Python tools."""
import re
from app.workflow_loader import load_workflows
from app.llm import choose_workflow
from app import tools

# Registry contains only executable capabilities, not workflow descriptions or steps.
# Workflow metadata and displayed step names are always loaded from the Excel workbook.
TOOL_REGISTRY = {
    "WF001": tools.inventory_restock,
    "WF002": tools.price_validation,
    "WF003": tools.process_vendor_file,
    "WF004": tools.product_description,
    "WF005": tools.order_status,
    "WF006": tools.duplicate_detection,
    "WF007": tools.campaign_brief,
    "WF008": tools.seo_keyword_classification,
    "WF009": tools.employee_task_assignment,
    "WF010": tools.performance_report,
}


def _step_list(workflow):
    """Read the execution plan from Excel; support arrow, newline, or numbered steps."""
    raw = str(workflow.get("Steps", "")).strip()
    parts = re.split(r"\s*(?:→|->|\n|\r\n)\s*", raw)
    cleaned = []
    for part in parts:
        part = re.sub(r"^\s*\d+[.)]\s*", "", part).strip()
        if part:
            cleaned.append(part)
    return cleaned


class WorkflowEngine:
    def __init__(self, workbook=None):
        self.workflows = load_workflows(workbook)

    def run(self, user_request, uploaded_file=None, workflow_override=None):
        if not user_request or not user_request.strip():
            return {"error": "Enter a user request.", "steps": []}
        try:
            if workflow_override:
                selected = next((w for w in self.workflows if w["Workflow_ID"] == workflow_override), None)
                if not selected:
                    return {"error": f"Unknown workflow override: {workflow_override}", "steps": []}
                routing = {"workflow_id": workflow_override, "reason": "Workflow selected manually for testing.", "missing_inputs": []}
            else:
                routing = choose_workflow(user_request, self.workflows)
        except Exception as exc:
            return {"error": str(exc), "steps": [{"step": "Workflow selection", "status": "failed", "detail": str(exc)}]}

        workflow_id = routing.get("workflow_id")
        if not workflow_id:
            return {"error": "No matching workflow was identified. Please describe the request in terms of one of the business workflows.", "routing": routing, "steps": []}
        workflow = next((w for w in self.workflows if w["Workflow_ID"] == workflow_id), None)
        if workflow is None:
            return {"error": f"Selected workflow {workflow_id} is not present in the workbook.", "steps": []}
        is_custom_response = str(workflow.get("Tools_Required", "")).strip().lower() == "custom_response"
        if workflow_id not in TOOL_REGISTRY and not is_custom_response:
            return {"selected_workflow": {"id": workflow_id, "name": workflow["Workflow_Name"]},
                    "error": f"Workflow {workflow_id} exists in Excel but has no registered execution tool. Add a tool and register it in TOOL_REGISTRY.",
                    "steps": [{"step": "Tool availability check", "status": "failed", "detail": "No executor registered."}]}

        steps = [{"step": "Identify workflow", "status": "completed",
                  "detail": f'{workflow_id} — {workflow["Workflow_Name"]}. Reason: {routing.get("reason", "")}'}]
        missing = routing.get("missing_inputs", [])
        if missing:
            steps.append({"step": "Validate required inputs", "status": "needs_input", "detail": "; ".join(map(str, missing))})

        try:
            if is_custom_response:
                result = {
                    "custom_workflow": True,
                    "workflow_id": workflow_id,
                    "message": str(workflow.get("Expected_Output", "")).strip(),
                    "user_request": user_request,
                    "note": "This no-code workflow returns the response configured in Excel. For data-changing or calculation tasks, implement a Python tool and register it in TOOL_REGISTRY.",
                }
            else:
                executor = TOOL_REGISTRY[workflow_id]
                if workflow_id == "WF003":
                    result = executor(uploaded_file=uploaded_file)
                elif workflow_id in {"WF004", "WF005", "WF007", "WF008", "WF009"}:
                    result = executor(user_request)
                else:
                    result = executor()

            # The step plan is read from Excel. A successful tool result means the
            # workflow executor completed its documented plan; conditions are shown separately.
            plan = _step_list(workflow)
            for index, label in enumerate(plan, 1):
                steps.append({"step": f"{index}. {label}", "status": "completed", "detail": "Handled by the workflow tool."})

            if isinstance(result, dict) and result.get("needs_input"):
                steps.append({"step": "Decision logic", "status": "needs_input",
                              "detail": result.get("message", "Additional input required.")})
            elif isinstance(result, dict) and result.get("found") is False:
                steps.append({"step": "Decision logic", "status": "needs_input", "detail": result.get("message", "Provide another identifier.")})
            elif isinstance(result, dict) and result.get("escalation"):
                steps.append({"step": "Decision logic", "status": "needs_input", "detail": result.get("message", "Escalation required.")})
            else:
                steps.append({"step": "Decision logic", "status": "completed", "detail": str(workflow.get("Decision_Logic", "Applied by workflow tool."))})
            return {"selected_workflow": {"id": workflow_id, "name": workflow["Workflow_Name"], "reason": routing.get("reason", "")},
                    "steps": steps, "result": result}
        except Exception as exc:
            steps.append({"step": "Tool execution", "status": "failed", "detail": f"{type(exc).__name__}: {exc}"})
            return {"selected_workflow": {"id": workflow_id, "name": workflow["Workflow_Name"], "reason": routing.get("reason", "")},
                    "steps": steps, "error": f"{type(exc).__name__}: {exc}"}
