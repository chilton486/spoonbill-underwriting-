import json
from unittest.mock import MagicMock

from app.models.practice_application import (
    PracticeApplication, OwnershipStructure, CashOnHandRange,
    FundingCadence, UnderwritingGrade,
)
from app.services.underwriting_score import (
    _score_production_scale, _score_payer_quality,
    _score_concentration_risk, _score_operational_maturity,
    _score_financial_stability, compute_underwriting_score,
    CASH_RANGE_VALUES,
)


def _make_app(**overrides):
    defaults = dict(
        gross_production_cents=0, net_collections_cents=0,
        years_in_operation=0, pct_ppo=0, pct_medicaid=0,
        estimated_denial_rate=0, avg_days_to_reimbursement=0,
        top_payers_json=None, avg_monthly_claim_count=0,
        dedicated_rcm_manager=False, written_billing_sop=False,
        billing_staff_count=0, practice_management_software=None,
        avg_ar_days=0, billing_model="IN_HOUSE",
        cash_on_hand_range=None, existing_loc_cents=0,
        prior_bankruptcy=False, pending_litigation=False,
        missed_loan_payments_24m=False, monthly_debt_payments_cents=0,
    )
    defaults.update(overrides)
    app = MagicMock(spec=PracticeApplication)
    for k, v in defaults.items():
        setattr(app, k, v)
    return app


class TestProductionScale:
    def test_zero_data_returns_zero(self):
        assert _score_production_scale(_make_app()) == 0

    def test_high_production_high_score(self):
        app = _make_app(
            gross_production_cents=200_000_00,
            net_collections_cents=150_000_00,
            years_in_operation=5,
        )
        score = _score_production_scale(app)
        assert score >= 80

    def test_moderate_production(self):
        app = _make_app(
            gross_production_cents=100_000_00,
            net_collections_cents=75_000_00,
            years_in_operation=3,
        )
        score = _score_production_scale(app)
        assert 40 <= score <= 80

    def test_capped_at_100(self):
        app = _make_app(
            gross_production_cents=500_000_00,
            net_collections_cents=500_000_00,
            years_in_operation=10,
        )
        assert _score_production_scale(app) <= 100


class TestPayerQuality:
    def test_baseline_with_zero_denial_and_ar(self):
        score = _score_payer_quality(_make_app())
        assert score == 75

    def test_high_ppo_low_denial_boosts(self):
        app = _make_app(pct_ppo=60, estimated_denial_rate=3, avg_days_to_reimbursement=25)
        score = _score_payer_quality(app)
        assert score >= 80

    def test_high_medicaid_high_denial_penalizes(self):
        app = _make_app(pct_medicaid=55, estimated_denial_rate=25, avg_days_to_reimbursement=70)
        score = _score_payer_quality(app)
        assert score <= 30

    def test_clamped_0_to_100(self):
        app = _make_app(pct_medicaid=80, estimated_denial_rate=30, avg_days_to_reimbursement=90)
        score = _score_payer_quality(app)
        assert 0 <= score <= 100


class TestConcentrationRisk:
    def test_no_payers_returns_baseline(self):
        assert _score_concentration_risk(_make_app()) == 70

    def test_diversified_payers_boosts(self):
        payers = [{"name": f"P{i}", "pct_revenue": 20} for i in range(5)]
        app = _make_app(top_payers_json=json.dumps(payers), avg_monthly_claim_count=500)
        score = _score_concentration_risk(app)
        assert score >= 85

    def test_single_dominant_payer_penalizes(self):
        payers = [{"name": "BigPayer", "pct_revenue": 60}]
        app = _make_app(top_payers_json=json.dumps(payers))
        score = _score_concentration_risk(app)
        assert score <= 50

    def test_invalid_json_handled(self):
        app = _make_app(top_payers_json="not json")
        score = _score_concentration_risk(app)
        assert score == 70


class TestOperationalMaturity:
    def test_bare_minimum(self):
        score = _score_operational_maturity(_make_app())
        assert score == 45

    def test_fully_mature(self):
        app = _make_app(
            dedicated_rcm_manager=True, written_billing_sop=True,
            billing_staff_count=3, practice_management_software="Open Dental",
            avg_ar_days=25, billing_model="IN_HOUSE",
        )
        score = _score_operational_maturity(app)
        assert score >= 90

    def test_known_pms_bonus(self):
        app = _make_app(practice_management_software="Dentrix")
        score_dentrix = _score_operational_maturity(app)
        app2 = _make_app(practice_management_software="SomeUnknown")
        score_unknown = _score_operational_maturity(app2)
        assert score_dentrix > score_unknown

    def test_high_ar_days_penalty(self):
        app = _make_app(avg_ar_days=65)
        score = _score_operational_maturity(app)
        assert score < 30


class TestFinancialStability:
    def test_baseline(self):
        assert _score_financial_stability(_make_app()) == 40

    def test_strong_finances(self):
        app = _make_app(
            cash_on_hand_range="250K_500K", existing_loc_cents=100_000_00,
            net_collections_cents=1_000_000_00, monthly_debt_payments_cents=5_000_00,
        )
        score = _score_financial_stability(app)
        assert score >= 75

    def test_bankruptcy_penalizes(self):
        app = _make_app(prior_bankruptcy=True)
        score = _score_financial_stability(app)
        assert score <= 20

    def test_all_negatives(self):
        app = _make_app(
            prior_bankruptcy=True, pending_litigation=True,
            missed_loan_payments_24m=True,
            net_collections_cents=100_000_00, monthly_debt_payments_cents=50_000_00,
        )
        score = _score_financial_stability(app)
        assert score == 0


class TestCompositeScoreAndGrade:
    def test_green_grade(self):
        app = _make_app(
            gross_production_cents=200_000_00, net_collections_cents=180_000_00,
            years_in_operation=5, pct_ppo=60, estimated_denial_rate=3,
            avg_days_to_reimbursement=25, avg_monthly_claim_count=500,
            dedicated_rcm_manager=True, written_billing_sop=True,
            billing_staff_count=3, practice_management_software="Open Dental",
            avg_ar_days=25, billing_model="IN_HOUSE",
            cash_on_hand_range="250K_500K", existing_loc_cents=100_000_00,
        )
        app.id = 1
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app
        result = compute_underwriting_score(db, 1)
        assert result["composite"] >= 75
        assert result["grade"] == "GREEN"

    def test_red_grade(self):
        app = _make_app(
            prior_bankruptcy=True, pending_litigation=True,
            missed_loan_payments_24m=True, pct_medicaid=60,
            estimated_denial_rate=25, avg_days_to_reimbursement=70,
        )
        app.id = 2
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app
        result = compute_underwriting_score(db, 2)
        assert result["composite"] < 50
        assert result["grade"] == "RED"

    def test_yellow_grade(self):
        app = _make_app(
            gross_production_cents=100_000_00, net_collections_cents=80_000_00,
            years_in_operation=3, pct_ppo=35, estimated_denial_rate=8,
            avg_days_to_reimbursement=40,
            dedicated_rcm_manager=True, practice_management_software="SomeOther",
            avg_ar_days=40, cash_on_hand_range="50K_100K",
        )
        app.id = 3
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app
        result = compute_underwriting_score(db, 3)
        assert 50 <= result["composite"] < 75
        assert result["grade"] == "YELLOW"

    def test_not_found_raises(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        try:
            compute_underwriting_score(db, 999)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "999" in str(e)

    def test_breakdown_has_all_components(self):
        app = _make_app()
        app.id = 4
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app
        result = compute_underwriting_score(db, 4)
        for key in ["production_scale", "payer_quality", "concentration_risk",
                     "operational_maturity", "financial_stability"]:
            assert key in result
            assert "score" in result[key]
            assert "weight" in result[key]
        assert "composite" in result
        assert "grade" in result

    def test_weights_sum_to_one(self):
        app = _make_app()
        app.id = 5
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app
        result = compute_underwriting_score(db, 5)
        total = sum(result[k]["weight"] for k in [
            "production_scale", "payer_quality", "concentration_risk",
            "operational_maturity", "financial_stability",
        ])
        assert abs(total - 1.0) < 0.001

    def test_stores_score_on_model(self):
        app = _make_app()
        app.id = 6
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = app
        compute_underwriting_score(db, 6)
        assert app.underwriting_score is not None
        assert app.underwriting_grade is not None
        assert app.underwriting_breakdown_json is not None
        db.commit.assert_called_once()


class TestNewEnums:
    def test_ownership_structure_values(self):
        expected = ["SOLE_PROPRIETOR", "PARTNERSHIP", "LLC", "S_CORP", "C_CORP", "DSO_AFFILIATED", "OTHER"]
        for v in expected:
            assert hasattr(OwnershipStructure, v)

    def test_cash_on_hand_range_values(self):
        expected = ["UNDER_25K", "R_25K_50K", "R_50K_100K", "R_100K_250K", "R_250K_500K", "OVER_500K"]
        for v in expected:
            assert hasattr(CashOnHandRange, v)

    def test_funding_cadence_values(self):
        expected = ["DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY"]
        for v in expected:
            assert hasattr(FundingCadence, v)

    def test_underwriting_grade_values(self):
        for g in ["GREEN", "YELLOW", "RED"]:
            assert hasattr(UnderwritingGrade, g)

    def test_cash_range_lookup(self):
        assert CASH_RANGE_VALUES["UNDER_25K"] == 12500
        assert CASH_RANGE_VALUES["OVER_500K"] == 750000


class TestSchemaFields:
    def test_underwriting_override_schema(self):
        from app.schemas.practice_application import UnderwritingScoreOverride
        fields = UnderwritingScoreOverride.model_fields
        assert "score" in fields
        assert "grade" in fields
        assert "reason" in fields

    def test_response_has_underwriting_fields(self):
        from app.schemas.practice_application import PracticeApplicationResponse
        fields = PracticeApplicationResponse.model_fields
        assert "underwriting_score" in fields
        assert "underwriting_grade" in fields
        assert "underwriting_breakdown_json" in fields

    def test_list_response_has_score(self):
        from app.schemas.practice_application import PracticeApplicationListResponse
        fields = PracticeApplicationListResponse.model_fields
        assert "underwriting_score" in fields
        assert "underwriting_grade" in fields
