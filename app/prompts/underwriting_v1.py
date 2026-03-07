"""Underwriting prompt template v1.

Instructs the model to act as a structured financial underwriting assistant
for dental insurance claim pre-funding.
"""

VERSION = "underwriting-v1"

SYSTEM_PROMPT = """You are a structured financial underwriting assistant for Spoonbill, a dental claims pre-funding platform.

Your role is to evaluate dental insurance claims for pre-funding eligibility. You reason over typed business objects and return ONLY schema-valid structured JSON output.

CRITICAL RULES:
1. You must return ONLY valid JSON matching the exact schema below. No markdown, no explanation outside JSON.
2. You must NOT invent facts not present in the input context.
3. When uncertain, explicitly surface uncertainty by recommending NEEDS_REVIEW rather than fabricating certainty.
4. You must reason about dental-specific risk factors: procedure complexity, payer behavior, documentation requirements, filing deadlines.
5. Risk scores range from 0.0 (lowest risk) to 1.0 (highest risk).
6. Confidence scores range from 0.0 (no confidence) to 1.0 (full confidence).
7. If the deterministic layer has already flagged hard-fail conditions (duplicate, missing fields), respect those signals.
8. You may refine the recommendation, risk score, advance rate, and add rationale, but you cannot override hard deterministic blocks.

OUTPUT SCHEMA (strict JSON):
{
  "recommendation": "APPROVE" | "DECLINE" | "NEEDS_REVIEW",
  "risk_score": <float 0.0-1.0>,
  "confidence_score": <float 0.0-1.0>,
  "suggested_advance_rate": <float 0.0-1.0 or null>,
  "suggested_max_advance_amount_cents": <int or null>,
  "fee_rate_suggestion": <float 0.0-0.2 or null>,
  "required_documents": [<string>, ...],
  "key_risk_factors": [
    {"factor": "<name>", "severity": "LOW"|"MEDIUM"|"HIGH", "detail": "<explanation>"}
  ],
  "rationale_summary": "<1-2 sentence operator-readable summary>",
  "rationale_detailed": "<detailed explanation of reasoning>",
  "policy_flags": [
    {"flag": "<flag_name>", "detail": "<explanation>"}
  ],
  "ontology_observations": [
    {"entity_type": "payer"|"provider"|"procedure"|"practice", "observation": "<text>", "confidence": <float>}
  ],
  "next_actions": [
    {"action": "<action>", "detail": "<text>", "priority": "LOW"|"MEDIUM"|"HIGH"}
  ]
}"""

USER_PROMPT_TEMPLATE = """Evaluate the following dental insurance claim for pre-funding eligibility.

CLAIM CONTEXT:
- Claim ID: {claim_id}
- Claim Token: {claim_token}
- Total Billed: ${total_billed_dollars}
- Procedure Date: {procedure_date}
- Claim Age: {claim_age_days} days

PRACTICE PROFILE:
- Name: {practice_name}
- State: {practice_state}
- PMS: {practice_pms}
- Total Claims: {practice_total_claims}
- Historical Denial Rate: {practice_denial_rate}
- Funding Utilization: {practice_utilization}

PAYER:
- Name: {payer_name}
- Plan Types: {payer_plan_types}
- EFT Capable: {payer_eft}
- ERA Capable: {payer_era}
- Filing Limit Days: {payer_filing_limit}
- Historical Denial Rate: {payer_denial_rate}
- Avg Cycle Days: {payer_avg_cycle}

{contract_section}

{provider_section}

PROCEDURE LINES:
{procedure_lines}

DETERMINISTIC UNDERWRITING SIGNALS:
- Decision: {deterministic_decision}
- Reasons: {deterministic_reasons}
- Duplicate Detected: {duplicate_detected}
- Missing Required Fields: {missing_fields}
- Amount Exceeds Threshold: {amount_exceeds}
- Inactive Contract: {inactive_contract}

Return your structured JSON assessment now."""


def format_user_prompt(input_data: dict) -> str:
    """Format the user prompt with claim context data."""
    # Build contract section
    contract = input_data.get("payer_contract")
    if contract:
        contract_section = f"""PAYER CONTRACT:
- Network Status: {contract.get('network_status', 'N/A')}
- Contract Status: {contract.get('status', 'N/A')}
- Filing Limit: {contract.get('timely_filing_limit_days', 'N/A')} days
- Effective: {contract.get('effective_start_date', 'N/A')} to {contract.get('effective_end_date', 'N/A')}"""
    else:
        contract_section = "PAYER CONTRACT: None on file"

    # Build provider section
    provider = input_data.get("provider")
    if provider:
        provider_section = f"""PROVIDER:
- Name: {provider.get('full_name', 'N/A')}
- NPI: {provider.get('npi', 'N/A')}
- Specialty: {provider.get('specialty', 'N/A')}
- Role: {provider.get('role', 'N/A')}"""
    else:
        provider_section = "PROVIDER: Not specified"

    # Build procedure lines
    lines = input_data.get("claim_lines", [])
    if lines:
        line_strs = []
        for i, line in enumerate(lines, 1):
            parts = [f"  Line {i}: {line.get('cdt_code', 'N/A')}"]
            if line.get("description"):
                parts.append(f"({line['description']})")
            parts.append(f"- Billed: ${line.get('billed_fee_cents', 0) / 100:.2f}")
            if line.get("tooth"):
                parts.append(f"- Tooth: {line['tooth']}")
            if line.get("common_denial_reasons"):
                parts.append(f"- Common Denials: {', '.join(line['common_denial_reasons'])}")
            if line.get("risk_notes"):
                parts.append(f"- Risk Notes: {line['risk_notes']}")
            line_strs.append(" ".join(parts))
        procedure_lines = "\n".join(line_strs)
    else:
        procedure_lines = "  No line-level detail available"

    det = input_data.get("deterministic", {})
    payer = input_data.get("payer", {})
    practice = input_data.get("practice", {})

    total_billed = input_data.get("total_billed_cents", 0)

    return USER_PROMPT_TEMPLATE.format(
        claim_id=input_data.get("claim_id", "N/A"),
        claim_token=input_data.get("claim_token", "N/A"),
        total_billed_dollars=f"{total_billed / 100:.2f}" if total_billed else "0.00",
        procedure_date=input_data.get("procedure_date", "N/A"),
        claim_age_days=input_data.get("claim_age_days", "N/A"),
        practice_name=practice.get("name", "N/A"),
        practice_state=practice.get("state", "N/A"),
        practice_pms=practice.get("pms_type", "N/A"),
        practice_total_claims=practice.get("total_claims", "N/A"),
        practice_denial_rate=f"{practice.get('historical_denial_rate', 0) * 100:.1f}%" if practice.get("historical_denial_rate") is not None else "N/A",
        practice_utilization=f"{practice.get('funding_utilization', 0) * 100:.0f}%" if practice.get("funding_utilization") is not None else "N/A",
        payer_name=payer.get("name", "N/A"),
        payer_plan_types=", ".join(payer.get("plan_types", [])) if payer.get("plan_types") else "N/A",
        payer_eft=payer.get("eft_capable", "N/A"),
        payer_era=payer.get("era_capable", "N/A"),
        payer_filing_limit=payer.get("filing_limit_days", "N/A"),
        payer_denial_rate=f"{input_data.get('historical_payer_denial_rate', 0) * 100:.1f}%" if input_data.get("historical_payer_denial_rate") is not None else "N/A",
        payer_avg_cycle=f"{input_data.get('historical_payer_avg_cycle_days', 0):.0f}" if input_data.get("historical_payer_avg_cycle_days") is not None else "N/A",
        contract_section=contract_section,
        provider_section=provider_section,
        procedure_lines=procedure_lines,
        deterministic_decision=det.get("decision", "N/A"),
        deterministic_reasons=str(det.get("reasons", [])),
        duplicate_detected=det.get("duplicate_detected", False),
        missing_fields=", ".join(det.get("missing_required_fields", [])) or "None",
        amount_exceeds=det.get("amount_exceeds_threshold", False),
        inactive_contract=det.get("inactive_contract", False),
    )
