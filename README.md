# Webvory — AI Agent Workflow Automation

A reusable Python + Gemini application that reads the supplied Excel workbook, selects one of its 10 workflows, runs Python tools, applies decision logic, and displays the selected workflow, execution steps, and final result.

## Requirements

- Python 3.10+
- Google Gemini API key
- Internet connection for Gemini routing and LLM-based workflows

## Setup (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and set `GEMINI_API_KEY` to your own key from an active Google AI Studio/Google Cloud project. Do not commit `.env` to GitHub. Restart Streamlit after changing it.

## Run

From the repository root:

```powershell
python -m streamlit run app/main.py
```

Open the local URL shown by Streamlit. Use **Gemini auto-select** for normal use. Manual test override is provided to test an individual workflow even when evaluating deterministic tool logic.


## Troubleshooting Gemini 403 `CONSUMER_SUSPENDED`

This response means Google has suspended the **project/consumer associated with that API key**. It is not a Python bug and changing the model name will not fix it.

1. Revoke/delete the exposed key in Google AI Studio / Google Cloud Console. Never paste API keys into chat, screenshots, GitHub, or Loom.
2. Open Google Cloud Console and check the associated project status, billing, and policy notices. Reactivate it if Google allows.
3. If that project cannot be restored, create/select a different active project, enable the **Generative Language API**, and create a new Gemini API key there.
4. Replace `GEMINI_API_KEY` in the project's `.env` file. Keep `GEMINI_MODEL=gemini-2.5-flash` unless the model is unavailable to your account.
5. Stop and restart Streamlit so the app reloads `.env`. The app now prioritizes the project-local `.env` over stale terminal environment variables and shows a readable error instead of dumping provider details.
6. Run `python -m pytest -q` to test offline workflow logic. For a Gemini live test, select **Gemini auto-select** after the key/project is fixed.

Until Gemini access is restored, use **Manual test override** to test deterministic workflows against the included mock CSV data. This does not replace Gemini for LLM-based content generation and should not be presented as a live Gemini demo.

## Tests

```powershell
python -m pytest -q
```

Tests validate workbook loading, the deterministic tools, conditions, and workflow registration. Live Gemini calls are not needed for unit tests.

## Architecture

1. `data/AI_Agent_Workflow_Assessment.xlsx` is the source of truth for workflow metadata, declared steps, decision rules, and assignment test prompts.
2. `app/llm.py` calls Gemini to route a natural-language request to one valid workflow ID. Gemini is also used for product SEO content, campaign briefs, and keyword classification.
3. `app/engine.py` is the reusable orchestrator. It validates the selected ID, dispatches to the Python tool registry, reads the displayed step plan from Excel, records the declared steps, and returns a structured result. Business rules are implemented in the corresponding tool functions; Excel is the workflow catalog, not an arbitrary code interpreter.
4. `app/tools.py` contains the ten workflow tools. Deterministic calculations and validation use Python; generation/classification use Gemini. Tool calls to unavailable business systems are simulated using CSV data.
5. `app/main.py` is the Streamlit interface showing workflow selection, steps, result JSON, and downloadable outputs.
6. Sample CSV files under `data/` simulate business systems/APIs where the assignment permits simulation.

## Implemented workflows

| ID | Workflow | Tool behavior |
|---|---|---|
| WF001 | Inventory Restock Check | Compares stock against minimum; suggests reorder quantity |
| WF002 | Product Price Validation | Joins by SKU; flags missing vendor prices and differences over 10% |
| WF003 | Vendor File Processing | Reads CSV/XLSX; normalizes columns; separates invalid SKU/product-name rows |
| WF004 | Product Description Generator | Gemini generates long/short descriptions and SEO metadata without inventing missing attributes |
| WF005 | Customer Order Status | Searches simulated order data by order ID/email; asks for another identifier if not found |
| WF006 | Duplicate Product Detection | Exact SKU matches are definite; high attribute/name similarity is flagged as likely |
| WF007 | Marketing Campaign Brief | Requests missing campaign goal/dates; Gemini creates the structured brief when inputs are present |
| WF008 | SEO Keyword Classification | Gemini assigns intent, category, priority, and target page |
| WF009 | Employee Task Assignment | Ranks available employees using skill match and remaining capacity; escalates if none fit |
| WF010 | Workflow Performance Report | Calculates success/failure rates, average duration, frequent errors, and flags failure rate >10% or average >5 seconds |

## Sample requests

- `Which products need restocking?`
- `Find products where vendor price differs by more than 10%.`
- `Process this vendor spreadsheet and show invalid rows.`
- `Generate SEO content for product: insulated water bottle, category: drinkware, material: stainless steel, color: blue, audience: commuters.`
- `Where is order ORD-1001?`
- `Find likely duplicate products in the catalog.`
- `Create a campaign brief. Goal: launch the new collection and increase sales. Audience: returning customers. Dates: 2026-11-01 to 2026-11-14. Products: winter collection.`
- `Classify these keywords: best running shoes, buy blue running shoes, Nike official website`
- `Assign this urgent Python API developer task to the best available developer. Deadline tomorrow.`
- `Which workflows are failing most often?`

## Adding an 11th workflow

- Add one workflow row to the Excel `Workflows` sheet using the same columns.
- Implement its tool function in `app/tools.py`.
- Register its workflow ID and callable in `TOOL_REGISTRY` in `app/engine.py`.
- Add a sample/test case.

The router catalog is loaded from Excel, so no separate routing prompt list needs to be maintained.

## Notes / boundaries

- This project uses Gemini only as its LLM provider.
- External business systems are simulated with local CSV data because credentials/API endpoints were not provided.
- Deterministic business rules run in Python rather than trusting generated text for calculations.
- Gemini API calls incur usage under the user's Google AI account and require a valid key.

## Validation status

Run `python -m pytest -q` from the project root. The current suite contains 26 offline tests, including mocked end-to-end execution of all 10 assignment prompts, workbook-driven step traces, vendor column aliases, price edge cases, keyword de-duplication/response validation, employee escalation, performance slow-step reporting, and readable Gemini error handling. Tests mock Gemini calls where needed and do **not** prove that a live Gemini API key is valid. After adding your own key to `.env`, test **Gemini auto-select** and the LLM-backed workflows. Live Gemini access depends on your Google project status, model availability, quota, and network.

## Known implementation boundary

Excel provides the workflow catalog and step plan, while each workflow's decision logic is implemented in a named Python tool. The orchestrator does not interpret arbitrary new Excel steps as executable code. Adding workflow 11 requires a new tool function plus one registry entry; its metadata and displayed steps then load from Excel. This keeps execution explicit and safer than evaluating arbitrary spreadsheet text.

## Quick launch on Windows

After installing dependencies and configuring `.env`, double-click `run_windows.bat`, or run `python -m streamlit run app/main.py` from this folder.


## Result display and expanded sample data

The Streamlit UI renders each workflow result as readable summaries, metrics, tables, and CSV downloads. Raw JSON is available only in the separate debugging expander. Sample datasets have been expanded with additional inventory, prices, duplicate-catalog examples, keywords, orders, employees, and execution logs so the demo produces richer results.

Run tests with `python -m pytest -q` (26 tests). These are offline/mocked tests; live Gemini access still requires an active Google Cloud project and a valid API key.


## Performance-report demo datasets

`data/workflow_logs.csv` is the **clean success-only demo dataset** used to demonstrate a 100% success rate in WF010. This is synthetic demonstration data, not measured production performance.

`data/workflow_logs_failure_scenarios.csv` preserves a mixed sample containing failures and errors for testing failure-rate flags, frequent errors, and slow-step detection. To demo failure analysis, back up `workflow_logs.csv` and replace it with `workflow_logs_failure_scenarios.csv` (renaming the latter to `workflow_logs.csv`), then restart Streamlit. Restore the clean demo file to show the success-only scenario.


## Important: interpreting WF010 success rate correctly

The default `data/workflow_logs.csv` is a **synthetic mixed-status sample dataset** with 133 records: 122 marked `success` and 11 marked `failure`. WF010 should therefore calculate a sample success rate of 91.73% and failure rate of 8.27% from this file. These are sample-log metrics, not a measured reliability claim about the application itself.

Do not change failure rows to `success` just to produce a 100% figure. A genuine 100% success rate is only supported when the complete, relevant execution log contains no failures; it still does not prove the system will be error-free in future. To report the application's actual reliability, run a representative end-to-end test suite and calculate passing tests / total tests separately from workflow execution success rates.


## WF002 loss-risk rule

`products.csv` price is treated as the selling price; `vendor_prices.csv` price is treated as vendor cost. If vendor cost exceeds selling price by any amount, WF002 flags `LOSS RISK` and reports the difference. This is no longer gated by a 10% threshold. Equal prices are break-even; vendor cost below selling price is not flagged by this specific rule. Missing vendor matches and invalid prices remain exceptions. Example: selling price ₹525 and vendor cost ₹549 means a ₹24 loss risk. This calculation does not include taxes, shipping, marketplace fees, or other costs unless added to the data.
