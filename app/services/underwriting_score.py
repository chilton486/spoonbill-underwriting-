import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.practice_application import PracticeApplication


CASH_RANGE_VALUES = {
    "UNDER_25K": 12500,
    "25K_50K": 37500,
    "50K_100K": 75000,
    "100K_250K": 175000,
    "250K_500K": 375000,
    "OVER_500K": 750000,
}


def _score_production_scale(app: PracticeApplication) -> int:
    gross = app.gross_production_cents or 0
    net = app.net_collections_cents or 0
    years = app.years_in_operation or 0

    score = 0
    if gross >= 200_000_00:
        score += 30
    elif gross >= 100_000_00:
        score += 20
    elif gross >= 50_000_00:
        score += 10

    if net >= 150_000_00:
        score += 30
    elif net >= 75_000_00:
        score += 20
    elif net >= 30_000_00:
        score += 10

    collection_ratio = (net / gross * 100) if gross > 0 else 0
    if collection_ratio >= 90:
        score += 20
    elif collection_ratio >= 80:
        score += 15
    elif collection_ratio >= 70:
        score += 10

    if years >= 5:
        score += 20
    elif years >= 3:
        score += 15
    elif years >= 1:
        score += 10

    return min(score, 100)


def _score_payer_quality(app: PracticeApplication) -> int:
    score = 50

    ppo = app.pct_ppo or 0
    medicaid = app.pct_medicaid or 0
    denial = app.estimated_denial_rate or 0
    days_reimb = app.avg_days_to_reimbursement or 0

    if ppo >= 50:
        score += 20
    elif ppo >= 30:
        score += 10

    if medicaid > 50:
        score -= 15
    elif medicaid > 30:
        score -= 5

    if denial <= 5:
        score += 15
    elif denial <= 10:
        score += 5
    elif denial > 20:
        score -= 10

    if 0 < days_reimb <= 30:
        score += 15
    elif days_reimb <= 45:
        score += 10
    elif days_reimb > 60:
        score -= 10

    return max(0, min(score, 100))


def _score_concentration_risk(app: PracticeApplication) -> int:
    score = 70

    try:
        payers = json.loads(app.top_payers_json) if app.top_payers_json else []
    except (json.JSONDecodeError, TypeError):
        payers = []

    if payers:
        max_pct = max((p.get("pct_revenue", 0) for p in payers), default=0)
        if max_pct > 50:
            score -= 30
        elif max_pct > 35:
            score -= 15
        elif max_pct <= 25:
            score += 15

        if len(payers) >= 4:
            score += 15
        elif len(payers) >= 2:
            score += 5

    claim_count = app.avg_monthly_claim_count or 0
    if claim_count >= 500:
        score += 10
    elif claim_count >= 200:
        score += 5

    return max(0, min(score, 100))


def _score_operational_maturity(app: PracticeApplication) -> int:
    score = 30

    if app.dedicated_rcm_manager:
        score += 20
    if app.written_billing_sop:
        score += 15
    if app.billing_staff_count and app.billing_staff_count >= 2:
        score += 10

    pms = (app.practice_management_software or "").lower()
    if pms in ("open dental", "open dental cloud", "dentrix", "eaglesoft", "curve dental"):
        score += 15
    elif pms:
        score += 5

    ar_days = app.avg_ar_days or 0
    if 0 < ar_days <= 30:
        score += 15
    elif ar_days <= 45:
        score += 10
    elif ar_days > 60:
        score -= 10

    if app.billing_model == "IN_HOUSE":
        score += 5

    return max(0, min(score, 100))


def _score_financial_stability(app: PracticeApplication) -> int:
    score = 40

    cash_range = app.cash_on_hand_range or ""
    cash_val = CASH_RANGE_VALUES.get(cash_range, 0)
    if cash_val >= 175000:
        score += 25
    elif cash_val >= 75000:
        score += 15
    elif cash_val >= 37500:
        score += 5

    if app.existing_loc_cents and app.existing_loc_cents > 0:
        score += 10

    if app.prior_bankruptcy:
        score -= 25
    if app.pending_litigation:
        score -= 15
    if app.missed_loan_payments_24m:
        score -= 20

    monthly_debt = app.monthly_debt_payments_cents or 0
    net = app.net_collections_cents or 0
    if net > 0:
        monthly_net = net / 12
        debt_ratio = monthly_debt / monthly_net if monthly_net > 0 else 1
        if debt_ratio <= 0.1:
            score += 10
        elif debt_ratio > 0.4:
            score -= 10

    return max(0, min(score, 100))


def compute_underwriting_score(db: Session, application_id: int) -> Dict[str, Any]:
    app = db.query(PracticeApplication).filter(
        PracticeApplication.id == application_id
    ).first()

    if not app:
        raise ValueError(f"Application {application_id} not found")

    production = _score_production_scale(app)
    payer_quality = _score_payer_quality(app)
    concentration = _score_concentration_risk(app)
    operational = _score_operational_maturity(app)
    financial = _score_financial_stability(app)

    weights = {
        "production_scale": 0.25,
        "payer_quality": 0.20,
        "concentration_risk": 0.15,
        "operational_maturity": 0.20,
        "financial_stability": 0.20,
    }

    composite = (
        production * weights["production_scale"]
        + payer_quality * weights["payer_quality"]
        + concentration * weights["concentration_risk"]
        + operational * weights["operational_maturity"]
        + financial * weights["financial_stability"]
    )

    composite = round(composite, 1)

    if composite >= 75:
        grade = "GREEN"
    elif composite >= 50:
        grade = "YELLOW"
    else:
        grade = "RED"

    breakdown = {
        "production_scale": {"score": production, "weight": weights["production_scale"]},
        "payer_quality": {"score": payer_quality, "weight": weights["payer_quality"]},
        "concentration_risk": {"score": concentration, "weight": weights["concentration_risk"]},
        "operational_maturity": {"score": operational, "weight": weights["operational_maturity"]},
        "financial_stability": {"score": financial, "weight": weights["financial_stability"]},
        "composite": composite,
        "grade": grade,
    }

    app.underwriting_score = composite
    app.underwriting_grade = grade
    app.underwriting_breakdown_json = json.dumps(breakdown)
    db.commit()

    return breakdown
