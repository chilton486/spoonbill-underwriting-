import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..services.audit import AuditService

logger = logging.getLogger(__name__)

BRIEF_SCHEMA_KEYS = {"summary", "key_drivers", "risks", "recommended_actions", "missing_data"}

SYSTEM_PROMPT = """You are a financial analyst for Spoonbill, a dental claims underwriting platform.
You receive a structured JSON snapshot of a dental practice's financial state.
Generate a concise brief with ONLY the data provided. Never invent numbers.

Output must be valid JSON with this exact schema:
{
  "summary": "2-3 sentence overview of the practice's financial position",
  "key_drivers": ["driver1", "driver2", ...],
  "risks": [
    {"risk": "description", "why": "explanation", "metric": "metric_name", "value": 0.0}
  ],
  "recommended_actions": [
    {"action": "ACTION_TYPE", "params": {}, "reason": "explanation"}
  ],
  "missing_data": ["item1", "item2"]
}

Valid action types: ADJUST_LIMIT, DIVERSIFY_PAYERS, REVIEW_DENIALS, MONITOR_EXCEPTIONS
Only recommend ADJUST_LIMIT if utilization > 0.85 or < 0.3.
Only output valid JSON. No markdown, no explanation outside the JSON."""


def generate_brief_from_context(context: dict) -> dict:
    settings = get_settings()

    if settings.openai_api_key:
        try:
            return _llm_generate(settings.openai_api_key, context)
        except Exception as e:
            logger.warning("LLM brief generation failed, falling back to template: %s", e)

    return _template_generate(context)


def _llm_generate(api_key: str, context: dict) -> dict:
    import httpx

    snapshot = context.get("snapshot", {})
    practice = context.get("practice", {})

    user_message = json.dumps({"practice": practice, "snapshot": snapshot}, default=str)

    for attempt in range(2):
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 1000,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        brief = json.loads(content)
        if _validate_brief(brief):
            return brief

    raise ValueError("LLM produced invalid brief after retries")


def _validate_brief(brief: dict) -> bool:
    if not isinstance(brief, dict):
        return False
    required = {"summary", "key_drivers", "risks", "recommended_actions", "missing_data"}
    return required.issubset(brief.keys())


def _template_generate(context: dict) -> dict:
    snapshot = context.get("snapshot", {})
    practice = context.get("practice", {})
    totals = snapshot.get("totals", {})
    funding = snapshot.get("funding", {})
    denials = snapshot.get("denials", {})
    risk_flags = snapshot.get("risk_flags", [])
    missing = snapshot.get("missing_data", [])
    payer_mix = snapshot.get("payer_mix", [])

    total_claims = totals.get("total_claims", 0)
    total_billed = totals.get("total_billed_cents", 0)
    funded = funding.get("total_funded_cents", 0)
    utilization = funding.get("utilization")
    denial_rate = denials.get("denial_rate", 0)

    summary_parts = [f"{practice.get('name', 'Practice')} has {total_claims} claims totaling ${total_billed/100:,.2f} billed."]
    if funded > 0:
        summary_parts.append(f"${funded/100:,.2f} funded to date.")
    if utilization is not None:
        summary_parts.append(f"Funding utilization at {utilization*100:.0f}%.")
    if denial_rate > 0:
        summary_parts.append(f"Denial rate: {denial_rate*100:.1f}%.")

    key_drivers = []
    if total_billed > 0:
        key_drivers.append(f"Total billed volume: ${total_billed/100:,.2f}")
    if payer_mix:
        key_drivers.append(f"Top payer: {payer_mix[0]['payer']} ({payer_mix[0]['share']*100:.0f}%)")
    if denial_rate > 0:
        key_drivers.append(f"Denial rate: {denial_rate*100:.1f}%")

    risks = []
    for flag in risk_flags:
        risks.append({
            "risk": flag.get("detail", flag.get("flag", "")),
            "why": f"Exceeds threshold of {flag.get('threshold', 'N/A')}",
            "metric": flag.get("metric", ""),
            "value": flag.get("value", 0),
        })

    recommended_actions = []
    if utilization is not None and utilization > 0.85:
        limit = funding.get("funding_limit_cents", 0)
        new_limit = int(limit * 1.25) if limit else 100000_00
        recommended_actions.append({
            "action": "ADJUST_LIMIT",
            "params": {"new_limit": new_limit},
            "reason": f"Utilization at {utilization*100:.0f}% — increase limit to maintain capacity",
        })
    if payer_mix and payer_mix[0]["share"] > 0.6:
        recommended_actions.append({
            "action": "DIVERSIFY_PAYERS",
            "params": {},
            "reason": f"Top payer concentration at {payer_mix[0]['share']*100:.0f}%",
        })
    if denial_rate > 0.1:
        recommended_actions.append({
            "action": "REVIEW_DENIALS",
            "params": {},
            "reason": f"Denial rate at {denial_rate*100:.1f}% exceeds 10% threshold",
        })

    return {
        "summary": " ".join(summary_parts),
        "key_drivers": key_drivers,
        "risks": risks,
        "recommended_actions": recommended_actions,
        "missing_data": missing,
    }
