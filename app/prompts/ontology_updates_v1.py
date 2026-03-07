"""Ontology update generation prompt template v1.

Instructs the model to propose structured ontology updates based on
claim outcomes, funding decisions, and remittance data.
"""

VERSION = "ontology-updates-v1"

SYSTEM_PROMPT = """You are a structured ontology intelligence assistant for Spoonbill, a dental claims pre-funding platform.

Your role is to analyze claim outcomes, funding decisions, and remittance data to propose structured updates to the practice ontology: payer behavior patterns, procedure code risk profiles, provider observations, and practice-level metrics.

CRITICAL RULES:
1. Return ONLY valid JSON matching the exact schema below. No markdown, no explanation outside JSON.
2. Do NOT invent observations not supported by the input data.
3. Proposed updates should be actionable and specific.
4. Include confidence scores for all observations. Low confidence (<0.5) items should be flagged for review.
5. Do not propose changes to financial ledger or payment data directly.
6. Focus on pattern recognition: denial trends, reimbursement shifts, cycle time anomalies, documentation gaps.
7. When evidence is limited, set review_needed=true and explain what additional data would help.

OUTPUT SCHEMA (strict JSON):
{
  "proposed_entity_updates": [
    {
      "entity_type": "payer" | "provider" | "procedure_code" | "practice" | "payer_contract",
      "entity_identifier": "<name, code, or ID>",
      "field": "<field to update>",
      "current_value": "<string or null>",
      "proposed_value": "<string>",
      "reason": "<explanation>",
      "confidence": <float 0.0-1.0>
    }
  ],
  "proposed_kpi_updates": [
    {
      "metric_name": "<metric>",
      "entity_type": "<type>",
      "entity_identifier": "<identifier>",
      "current_value": <float or null>,
      "proposed_value": <float>,
      "direction": "INCREASE" | "DECREASE" | "STABLE",
      "reason": "<explanation>"
    }
  ],
  "risk_flags": [
    {
      "entity_type": "<type>",
      "entity_identifier": "<identifier>",
      "flag_type": "<e.g. HIGH_DENIAL_RATE, SLOW_CYCLE_TIME, UNDERPAYMENT>",
      "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
      "detail": "<explanation>",
      "recommended_action": "<action or null>"
    }
  ],
  "payer_observations": [
    {
      "entity_type": "payer",
      "entity_identifier": "<payer name>",
      "observation": "<text>",
      "evidence": "<text or null>",
      "confidence": <float 0.0-1.0>
    }
  ],
  "procedure_observations": [
    {
      "entity_type": "procedure_code",
      "entity_identifier": "<CDT code>",
      "observation": "<text>",
      "evidence": "<text or null>",
      "confidence": <float 0.0-1.0>
    }
  ],
  "provider_observations": [
    {
      "entity_type": "provider",
      "entity_identifier": "<provider name>",
      "observation": "<text>",
      "evidence": "<text or null>",
      "confidence": <float 0.0-1.0>
    }
  ],
  "practice_observations": [
    {
      "entity_type": "practice",
      "entity_identifier": "<practice name>",
      "observation": "<text>",
      "evidence": "<text or null>",
      "confidence": <float 0.0-1.0>
    }
  ],
  "review_needed": <boolean>,
  "overall_confidence": <float 0.0-1.0>,
  "summary": "<brief summary of all proposed updates>"
}"""

USER_PROMPT_TEMPLATE = """Analyze the following claim and outcome data to propose ontology updates.

PRACTICE CONTEXT:
- Practice: {practice_name} (ID: {practice_id})
- Total Claims: {practice_total_claims}
- Practice Denial Rate: {practice_denial_rate}
- Avg Cycle Days: {practice_avg_cycle_days}

{claim_section}

{funding_section}

{remittance_section}

{payer_section}

{provider_section}

{procedure_section}

Return your structured JSON ontology update proposals now."""


def format_user_prompt(input_data: dict) -> str:
    """Format the ontology update prompt with input data."""
    # Claim section
    claim_parts = []
    if input_data.get("claim_id"):
        claim_parts.append(f"- Claim ID: {input_data['claim_id']}")
    if input_data.get("claim_status"):
        claim_parts.append(f"- Status: {input_data['claim_status']}")
    if input_data.get("claim_total_billed_cents") is not None:
        claim_parts.append(f"- Total Billed: ${input_data['claim_total_billed_cents'] / 100:.2f}")
    if input_data.get("claim_total_paid_cents") is not None:
        claim_parts.append(f"- Total Paid: ${input_data['claim_total_paid_cents'] / 100:.2f}")
    if input_data.get("claim_payer"):
        claim_parts.append(f"- Payer: {input_data['claim_payer']}")
    lines = input_data.get("claim_lines", [])
    if lines:
        claim_parts.append("- Procedures:")
        for line in lines:
            code = line.get("cdt_code", "N/A")
            desc = line.get("description", "")
            billed = line.get("billed_fee_cents", 0)
            claim_parts.append(f"  - {code} {desc} (${billed / 100:.2f})")
    claim_section = "CLAIM DATA:\n" + "\n".join(claim_parts) if claim_parts else "CLAIM DATA: Not provided"

    # Funding section
    funding_parts = []
    if input_data.get("funding_decision"):
        funding_parts.append(f"- Decision: {input_data['funding_decision']}")
    if input_data.get("risk_score") is not None:
        funding_parts.append(f"- Risk Score: {input_data['risk_score']:.3f}")
    if input_data.get("advance_rate") is not None:
        funding_parts.append(f"- Advance Rate: {input_data['advance_rate'] * 100:.0f}%")
    funding_section = "FUNDING DECISION:\n" + "\n".join(funding_parts) if funding_parts else "FUNDING DECISION: Not available"

    # Remittance section
    rem_parts = []
    if input_data.get("remittance_total_paid_cents") is not None:
        rem_parts.append(f"- Total Paid: ${input_data['remittance_total_paid_cents'] / 100:.2f}")
    if input_data.get("remittance_total_adjustments_cents") is not None:
        rem_parts.append(f"- Total Adjustments: ${input_data['remittance_total_adjustments_cents'] / 100:.2f}")
    if input_data.get("remittance_match_rate") is not None:
        rem_parts.append(f"- Match Rate: {input_data['remittance_match_rate'] * 100:.0f}%")
    if input_data.get("denial_codes"):
        rem_parts.append(f"- Denial Codes: {', '.join(input_data['denial_codes'])}")
    remittance_section = "REMITTANCE DATA:\n" + "\n".join(rem_parts) if rem_parts else "REMITTANCE DATA: Not available"

    # Payer section
    payer_parts = []
    if input_data.get("payer_name"):
        payer_parts.append(f"- Name: {input_data['payer_name']}")
    if input_data.get("payer_denial_rate") is not None:
        payer_parts.append(f"- Denial Rate: {input_data['payer_denial_rate'] * 100:.1f}%")
    payer_section = "PAYER CONTEXT:\n" + "\n".join(payer_parts) if payer_parts else "PAYER CONTEXT: Not available"

    # Provider section
    provider_section = f"PROVIDER: {input_data['provider_name']}" if input_data.get("provider_name") else "PROVIDER: Not specified"

    # Procedure section
    codes = input_data.get("procedure_codes", [])
    procedure_section = f"PROCEDURE CODES: {', '.join(codes)}" if codes else "PROCEDURE CODES: Not specified"

    return USER_PROMPT_TEMPLATE.format(
        practice_name=input_data.get("practice_name", "N/A"),
        practice_id=input_data.get("practice_id", "N/A"),
        practice_total_claims=input_data.get("practice_total_claims", "N/A"),
        practice_denial_rate=f"{input_data['practice_denial_rate'] * 100:.1f}%" if input_data.get("practice_denial_rate") is not None else "N/A",
        practice_avg_cycle_days=f"{input_data['practice_avg_cycle_days']:.0f}" if input_data.get("practice_avg_cycle_days") is not None else "N/A",
        claim_section=claim_section,
        funding_section=funding_section,
        remittance_section=remittance_section,
        payer_section=payer_section,
        provider_section=provider_section,
        procedure_section=procedure_section,
    )
