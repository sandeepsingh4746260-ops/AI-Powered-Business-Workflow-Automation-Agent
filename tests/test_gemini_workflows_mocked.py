"""Offline contract tests for workflows that call Gemini; no API key required."""
from app import tools


def test_product_description_uses_text_generator(monkeypatch):
    monkeypatch.setattr(tools, "generate_text", lambda prompt: "SEO content; missing fields marked Not provided.")
    result = tools.product_description("Generate SEO content for a blue bottle")
    assert "Not provided" in result["content"]


def test_campaign_brief_requires_goal_and_dates():
    result = tools.campaign_brief("Create a campaign brief")
    assert result["needs_input"] is True
    assert set(result["missing_inputs"]) == {"campaign goal", "campaign dates"}


def test_campaign_brief_calls_generator_when_inputs_present(monkeypatch):
    monkeypatch.setattr(tools, "generate_text", lambda prompt: "Objective, channels, timeline, checklist")
    result = tools.campaign_brief("Launch collection to increase sales from 2026-11-01 to 2026-11-14")
    assert result["needs_input"] is False
    assert "timeline" in result["brief"]


def test_keyword_classification_contract(monkeypatch):
    def fake_classify(keywords, context):
        return [{"keyword": k, "intent": "commercial", "category": context,
                 "priority": "Medium", "recommended_target_page": "/category"} for k in keywords]
    monkeypatch.setattr(tools, "classify_keywords", fake_classify)
    result = tools.seo_keyword_classification("Classify keywords: running shoes, buy running shoes")
    assert result["count"] == 2
    assert {x["keyword"] for x in result["classifications"]} == {"running shoes", "buy running shoes"}
