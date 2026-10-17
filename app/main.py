import json
import re
from pathlib import Path
import pandas as pd
import streamlit as st
from app.engine import WorkflowEngine
from app.workflow_loader import load_workflows, load_test_questions, create_custom_workflow, delete_custom_workflow

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Webvory AI Workflow Agent", page_icon="⚙️", layout="wide")
st.title("AI Agent Workflow Automation")
st.caption("Reusable workflow engine • Excel-driven workflow catalog • Gemini-powered routing and content generation")

try:
    engine = WorkflowEngine()
    workflows = engine.workflows
except Exception as exc:
    st.error(f"Could not load workflow workbook: {exc}")
    st.stop()

with st.sidebar:
    st.header("Workflow catalog")
    st.write(f"Loaded **{len(workflows)} workflows** from the Excel source.")
    st.dataframe(pd.DataFrame([{"ID": w["Workflow_ID"], "Workflow": w["Workflow_Name"]} for w in workflows]),
                 use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("Test requests from assignment")
    try:
        questions = load_test_questions()
        chosen = st.selectbox("Choose an example", [""] + [q["Test_Request"] for q in questions])
    except Exception:
        chosen = ""

request = st.text_area("User request", value=chosen, height=110,
                       placeholder="Example: Which products need restocking?")
upload = st.file_uploader("Optional vendor file (WF003 only)", type=["csv", "xlsx", "xls"])
manual = st.selectbox("Workflow selection mode", ["Gemini auto-select", "Manual test override"])
override = None
if manual == "Manual test override":
    override = st.selectbox("Choose workflow", [w["Workflow_ID"] for w in workflows],
                            format_func=lambda x: next(w["Workflow_Name"] for w in workflows if w["Workflow_ID"] == x))

if st.button("Run agent", type="primary", use_container_width=True):
    if not request.strip():
        st.warning("Enter a request first.")
    else:
        with st.spinner("Selecting workflow and executing tools..."):
            output = engine.run(request, uploaded_file=upload, workflow_override=override)
        st.session_state["last_output"] = output

output = st.session_state.get("last_output")
if output:
    st.divider()
    if output.get("selected_workflow"):
        st.subheader("Selected workflow")
        st.write(f'**{output["selected_workflow"]["id"]} — {output["selected_workflow"]["name"]}**')
        st.caption(output["selected_workflow"].get("reason", ""))
    st.subheader("Steps executed")
    for i, step in enumerate(output.get("steps", []), 1):
        status = step["status"]
        icon = "✅" if status == "completed" else "⚠️" if status == "needs_input" else "❌"
        st.write(f'{i}. {icon} **{step["step"]}** — {step["detail"]}')
    st.subheader("Final result")
    if output.get("error"):
        st.error(output["error"])
    if output.get("result") is not None:
        result = output["result"]
        workflow_id = output.get("selected_workflow", {}).get("id")

        def show_table(title, rows, key):
            if isinstance(rows, list) and rows:
                st.markdown(f"**{title}**")
                st.dataframe(pd.json_normalize(rows), use_container_width=True, hide_index=True)
                st.download_button(f"Download {title} CSV", pd.json_normalize(rows).to_csv(index=False).encode("utf-8"), f"{key}.csv", "text/csv", key=f"dl_{key}")
            elif isinstance(rows, list):
                st.info(f"{title}: no records")

        def show_result(result, workflow_id):
            if not isinstance(result, dict):
                st.write(result)
                return
            # WF004: present generated copy as distinct readable sections.
            if workflow_id == "WF004":
                if result.get("missing_attributes"):
                    st.warning("Missing product information: " + ", ".join(result["missing_attributes"]))
                content = result.get("content", "")
                if content:
                    # Render structured markdown normally, not as escaped JSON.
                    st.markdown(content.replace("\\n", "\n"))
                if result.get("validation_note"):
                    st.info(result["validation_note"])
                return

            # Workflow-specific, human-readable business summaries and tables.
            if workflow_id == "WF001":
                st.metric("Products needing restock", result.get("count", len(result.get("restock_products", []))))
                show_table("Restock list", result.get("restock_products", []), "restock_list")
            elif workflow_id == "WF002":
                st.metric("Price exceptions", result.get("exception_count", len(result.get("exceptions", []))))
                show_table("Price validation results", result.get("rows", []), "price_validation")
                show_table("Exceptions requiring review", result.get("exceptions", []), "price_exceptions")
            elif workflow_id == "WF003":
                st.success(f"Clean rows: {result.get('cleaned_count', len(result.get('cleaned_rows', [])))} · Invalid rows: {result.get('invalid_count', len(result.get('invalid_rows', [])))}")
                show_table("Cleaned vendor data", result.get("cleaned_rows", []), "cleaned_vendor_data")
                show_table("Invalid vendor rows", result.get("invalid_rows", []), "invalid_vendor_rows")
            elif workflow_id == "WF005":
                if result.get("found") is False:
                    st.warning(result.get("message", "No matching order found."))
                else:
                    show_table("Order and shipment details", result.get("orders", []), "order_status")
            elif workflow_id == "WF006":
                groups = result.get("duplicate_groups", [])
                st.metric("Potential duplicate groups", result.get("group_count", len(groups)))
                if groups:
                    flat = []
                    for group_no, group in enumerate(groups, 1):
                        primary = group.get("primary_product", {})
                        for match in group.get("matches", []):
                            flat.append({"group": group_no, "primary_sku": primary.get("sku"), "primary_product": primary.get("product_name"), "match_sku": match.get("product", {}).get("sku"), "match_product": match.get("product", {}).get("product_name"), "confidence": match.get("confidence"), "reason": match.get("reason")})
                    show_table("Duplicate matches", flat, "duplicate_matches")
                else:
                    st.success("No likely duplicates found.")
            elif workflow_id == "WF007":
                if result.get("needs_input"):
                    st.warning(result.get("message", "More campaign details are required."))
                else:
                    st.markdown(result.get("brief", "No campaign brief returned."))
            elif workflow_id == "WF008":
                st.metric("Unique keywords classified", result.get("count", len(result.get("classifications", []))))
                st.caption(f"Duplicates removed: {result.get('duplicates_removed', 0)}")
                show_table("Keyword classification report", result.get("classifications", []), "keyword_classification")
            elif workflow_id == "WF009":
                if result.get("assigned"):
                    st.success(f"Recommended employee: {result.get('recommended_employee')}")
                    st.write(result.get("reason", ""))
                    st.write(f"Priority: {result.get('priority', 'Not specified')} · Deadline: {result.get('deadline', 'Not specified')}")
                    show_table("Ranked candidates", result.get("ranked_candidates", []), "ranked_candidates")
                else:
                    st.warning(result.get("message", "Task needs more information or escalation."))
                    show_table("Available candidates", result.get("candidates", []), "assignment_candidates")
            elif workflow_id == "WF010":
                st.metric("Total executions", result.get("total_runs", 0))
                c1, c2 = st.columns(2)
                c1.metric("Success rate", f"{result.get('success_rate_percent', 0)}%")
                c2.metric("Failure rate", f"{result.get('failure_rate_percent', 0)}%")
                st.caption(f"Slow-step threshold: {result.get('slow_step_threshold_seconds', 0)} seconds")
                show_table("Workflow performance", result.get("workflows", []), "workflow_performance")
                show_table("Slow steps", result.get("slow_steps", []), "slow_steps")
            else:
                # Generic nested-result renderer: avoid dumping complex JSON as the primary view.
                for key, value in result.items():
                    title = key.replace("_", " ").title()
                    if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                        show_table(title, value, re.sub(r"[^a-z0-9]+", "_", key.lower()))
                    elif isinstance(value, dict):
                        with st.expander(title):
                            st.dataframe(pd.json_normalize(value), use_container_width=True, hide_index=True)
                    elif isinstance(value, (str, int, float, bool)) or value is None:
                        st.markdown(f"**{title}:** {value if value is not None else '—'}")
                    else:
                        st.write(f"**{title}**")
                        st.write(value)

        show_result(result, workflow_id)

    with st.expander("Raw execution result JSON"):
        st.code(json.dumps(output, indent=2, ensure_ascii=False), language="json")

st.divider()
st.subheader("Architecture")
st.code("User request → Gemini workflow router → reusable workflow engine → Python tools / Gemini content tools → conditions & errors → result + execution trace", language="text")
st.caption("Adding a workflow: add a row to the Excel Workflows sheet, implement its tool, and register its executor in app/engine.py.")
