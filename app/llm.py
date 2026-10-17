import json
from app.config import GEMINI_API_KEY, GEMINI_MODEL

class GeminiUnavailable(RuntimeError):
    pass

def _client():
    if not GEMINI_API_KEY or GEMINI_API_KEY in {"your_google_gemini_api_key_here", "YOUR_GEMINI_API_KEY"}:
        raise GeminiUnavailable(
            "GEMINI_API_KEY is missing or still set to the example placeholder. "
            "Create a valid Gemini API key in an active Google AI Studio/Google Cloud project, "
            "then put it in the project .env file and restart Streamlit."
        )
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiUnavailable("Gemini SDK missing. Run: python -m pip install -r requirements.txt") from exc
    return genai.Client(api_key=GEMINI_API_KEY)

def _friendly_api_error(exc):
    """Turn provider errors into actionable messages without echoing secrets."""
    raw = str(exc)
    upper = raw.upper()
    if "CONSUMER_SUSPENDED" in upper or ("403" in upper and "SUSPENDED" in upper):
        return GeminiUnavailable(
            "Gemini API rejected this key because its Google Cloud consumer project is SUSPENDED (403 CONSUMER_SUSPENDED). "
            "This cannot be fixed by changing the model name or retrying the same key. "
            "In Google Cloud Console, check/reactivate the project and its billing/policy status, or create a key under a different active project. "
            "Then replace GEMINI_API_KEY in this project's .env file and restart Streamlit. "
            "The key shown in the error should be revoked because it has been exposed. "
            "For local testing meanwhile, choose 'Manual test override' to run deterministic/mock-data workflows without Gemini routing."
        )
    if "API_KEY_INVALID" in upper or ("API KEY" in upper and ("INVALID" in upper or "NOT VALID" in upper)):
        return GeminiUnavailable(
            "Gemini rejected the API key. Create/check the key in Google AI Studio, ensure the Generative Language API is enabled for its project, "
            "update GEMINI_API_KEY in .env, and restart Streamlit. Do not share the key publicly."
        )
    if "RESOURCE_EXHAUSTED" in upper or "QUOTA" in upper:
        return GeminiUnavailable(
            "Gemini quota/rate limit reached. Check the project's API quota and billing, then retry later or use an available model."
        )
    if "NOT_FOUND" in upper and "MODEL" in upper:
        return GeminiUnavailable(
            f"Gemini model '{GEMINI_MODEL}' was not found or is not available to this key. Check the model name and model access in Google AI Studio, then update GEMINI_MODEL in .env."
        )
    if "PERMISSION_DENIED" in upper or "403" in upper:
        return GeminiUnavailable(
            "Gemini returned a permission error. Check that the key belongs to the intended active project and that the Generative Language API is enabled. "
            "Update .env and restart Streamlit. Provider details were hidden to avoid exposing credentials."
        )
    return GeminiUnavailable(
        f"Gemini request failed ({type(exc).__name__}). Check internet access, model availability, and Google AI Studio project status. "
        "Sensitive provider response details are hidden; see terminal logs only after removing any API keys."
    )

def _generate_content(*, model, contents, config=None):
    client = _client()
    try:
        if config is None:
            return client.models.generate_content(model=model, contents=contents)
        return client.models.generate_content(model=model, contents=contents, config=config)
    except Exception as exc:
        raise _friendly_api_error(exc) from None

def choose_workflow(user_request, workflows):
    """Use Gemini to select a workflow ID. Execution remains controlled by Python tools."""
    catalog = [
        {"Workflow_ID": w["Workflow_ID"], "Workflow_Name": w["Workflow_Name"],
         "Trigger": w["Trigger"], "Inputs": w["Inputs"]}
        for w in workflows
    ]
    prompt = f"""
You are a workflow router. Select exactly one workflow from this catalog for the user request.
Only select an ID that exists in the catalog. If no workflow fits, use null.
Return ONLY valid JSON with keys: workflow_id, reason, missing_inputs.
missing_inputs must be a JSON array of concise strings. Do not execute the workflow.
Catalog: {json.dumps(catalog, ensure_ascii=False)}
User request: {user_request}
"""
    response = _generate_content(model=GEMINI_MODEL, contents=prompt, config={"response_mime_type": "application/json"})
    try:
        result = json.loads(response.text)
    except Exception as exc:
        raise RuntimeError(f"Gemini returned invalid routing JSON: {response.text}") from exc
    allowed = {w["Workflow_ID"] for w in workflows}
    workflow_id = result.get("workflow_id")
    if workflow_id is not None and workflow_id not in allowed:
        raise RuntimeError(f"Gemini selected unknown workflow ID: {workflow_id}")
    return {
        "workflow_id": workflow_id,
        "reason": str(result.get("reason", "")),
        "missing_inputs": result.get("missing_inputs", []) if isinstance(result.get("missing_inputs", []), list) else []
    }

def generate_text(prompt):
    response = _generate_content(model=GEMINI_MODEL, contents=prompt)
    return (response.text or "").strip()

def classify_keywords(keywords, product_context=""):
    prompt = f"""
Classify every keyword into one of informational, commercial, transactional, navigational.
Return ONLY a JSON array. Each item: keyword, intent, category, priority (High/Medium/Low), recommended_target_page.
Do not omit or invent keywords. Product/category context: {product_context}
Keywords: {json.dumps(keywords, ensure_ascii=False)}
"""
    response = _generate_content(model=GEMINI_MODEL, contents=prompt, config={"response_mime_type": "application/json"})
    try:
        result = json.loads(response.text)
        if not isinstance(result, list):
            raise ValueError("Expected a JSON array.")
        return result
    except Exception as exc:
        raise RuntimeError(f"Gemini returned invalid keyword classification JSON: {response.text}") from exc
