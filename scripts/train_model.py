#!/usr/bin/env python3
"""Model training foundation for Spoonbill claim underwriting.

Trains baseline models on synthetic (or real) claim data to predict:
- Funding decision: APPROVE / DENY / NEEDS_REVIEW
- Risk score: probability of denial or payment delay

IMPORTANT: This model is trained on SYNTHETIC data and is NOT a production
underwriting engine. It validates data pipelines, feature design, and model
interfaces in preparation for real practice data.

Requirements (install separately):
    pip install scikit-learn numpy pandas joblib

Usage:
    python scripts/train_model.py [--output-dir models/] [--practice-id N]
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Check for ML dependencies
try:
    import numpy as np
    import pandas as pd
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.metrics import (
        classification_report, accuracy_score, roc_auc_score,
        confusion_matrix, precision_recall_fscore_support,
    )
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning(
        "ML dependencies not installed. Install with:\n"
        "  pip install scikit-learn numpy pandas joblib\n"
        "Exiting."
    )


def extract_features(db_session) -> pd.DataFrame:
    """Extract training features from claim data in the database.

    Features extracted:
    - total_billed_cents: Total billed amount
    - total_allowed_cents: Total allowed amount
    - num_claim_lines: Number of line items
    - payer_denial_rate: Historical denial rate for this payer
    - provider_claim_volume: Number of claims by this provider
    - days_since_submission: Age of the claim
    - has_payer_contract: Whether a payer contract exists
    - procedure_category_mix: Distribution of procedure categories
    - is_medicaid: Whether payer is Medicaid
    - billed_to_allowed_ratio: Ratio of billed to allowed amounts
    """
    from sqlalchemy import func
    from app.database import SessionLocal
    from app.models.claim import Claim
    from app.models.claim_line import ClaimLine
    from app.models.funding_decision import FundingDecision
    from app.models.payer import Payer
    from app.models.procedure_code import ProcedureCode

    logger.info("Extracting features from database...")

    # Get all claims with funding decisions
    claims_with_decisions = (
        db_session.query(
            Claim.id.label("claim_id"),
            Claim.practice_id,
            Claim.payer_id,
            Claim.provider_id,
            Claim.payer_contract_id,
            Claim.total_billed_cents,
            Claim.total_allowed_cents,
            Claim.total_paid_cents,
            Claim.amount_cents,
            Claim.submitted_at,
            Claim.adjudicated_at,
            Claim.date_of_service,
            Claim.status,
            FundingDecision.decision,
            FundingDecision.risk_score.label("actual_risk_score"),
        )
        .join(FundingDecision, FundingDecision.claim_id == Claim.id)
        .all()
    )

    if not claims_with_decisions:
        logger.warning("No claims with funding decisions found. Run synthetic data generation first.")
        return pd.DataFrame()

    logger.info("Found %d claims with funding decisions", len(claims_with_decisions))

    # Pre-compute payer denial rates
    payer_stats = {}
    all_claims = db_session.query(Claim.payer_id, Claim.status).filter(Claim.payer_id.isnot(None)).all()
    for payer_id, status in all_claims:
        if payer_id not in payer_stats:
            payer_stats[payer_id] = {"total": 0, "denied": 0}
        payer_stats[payer_id]["total"] += 1
        if status in ("declined", "DECLINED"):
            payer_stats[payer_id]["denied"] += 1

    # Pre-compute provider claim volumes
    provider_volumes = {}
    provider_claims = db_session.query(Claim.provider_id, func.count(Claim.id)).filter(
        Claim.provider_id.isnot(None)
    ).group_by(Claim.provider_id).all()
    for provider_id, count in provider_claims:
        provider_volumes[provider_id] = count

    # Pre-compute claim line counts and category info
    claim_line_info = {}
    claim_lines = (
        db_session.query(
            ClaimLine.claim_id,
            func.count(ClaimLine.id).label("line_count"),
        )
        .group_by(ClaimLine.claim_id)
        .all()
    )
    for claim_id, line_count in claim_lines:
        claim_line_info[claim_id] = line_count

    # Get payer plan types for Medicaid detection
    payer_types = {}
    payers = db_session.query(Payer.id, Payer.plan_types).all()
    for payer_id, plan_types in payers:
        payer_types[payer_id] = plan_types or []

    # Build feature rows
    rows = []
    now = datetime.utcnow()

    for c in claims_with_decisions:
        billed = c.total_billed_cents or c.amount_cents or 0
        allowed = c.total_allowed_cents or 0

        # Payer denial rate
        payer_stat = payer_stats.get(c.payer_id, {"total": 1, "denied": 0})
        payer_denial_rate = payer_stat["denied"] / max(payer_stat["total"], 1)

        # Provider volume
        provider_volume = provider_volumes.get(c.provider_id, 0)

        # Days since submission
        days_since = 0
        if c.submitted_at:
            days_since = (now - c.submitted_at).days

        # Cycle days (submission to adjudication)
        cycle_days = None
        if c.submitted_at and c.adjudicated_at:
            cycle_days = (c.adjudicated_at - c.submitted_at).days

        # Payer is Medicaid
        is_medicaid = 1 if any("Medicaid" in str(pt) for pt in payer_types.get(c.payer_id, [])) else 0

        # Billed-to-allowed ratio
        billed_to_allowed = billed / max(allowed, 1)

        # Number of claim lines
        num_lines = claim_line_info.get(c.claim_id, 1)

        row = {
            "claim_id": c.claim_id,
            "total_billed_cents": billed,
            "total_allowed_cents": allowed,
            "num_claim_lines": num_lines,
            "payer_denial_rate": payer_denial_rate,
            "provider_claim_volume": provider_volume,
            "days_since_submission": days_since,
            "has_payer_contract": 1 if c.payer_contract_id else 0,
            "is_medicaid": is_medicaid,
            "billed_to_allowed_ratio": billed_to_allowed,
            "cycle_days": cycle_days or 0,
            # Target
            "decision": c.decision,
            "actual_risk_score": c.actual_risk_score,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    logger.info("Feature matrix: %d rows, %d columns", len(df), len(df.columns))
    return df


def train_models(
    df: pd.DataFrame,
    output_dir: str,
) -> Dict[str, Any]:
    """Train baseline models on extracted features.

    Models trained:
    1. Logistic Regression (interpretable baseline)
    2. Gradient Boosting Classifier (performance baseline)
    3. Random Forest Classifier (ensemble baseline)

    Returns evaluation report.
    """
    if df.empty:
        logger.error("No data to train on")
        return {}

    os.makedirs(output_dir, exist_ok=True)

    # Feature columns
    feature_cols = [
        "total_billed_cents", "total_allowed_cents", "num_claim_lines",
        "payer_denial_rate", "provider_claim_volume", "days_since_submission",
        "has_payer_contract", "is_medicaid", "billed_to_allowed_ratio",
    ]

    X = df[feature_cols].fillna(0)
    y = df["decision"]

    # Encode target
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )

    logger.info("Training set: %d, Test set: %d", len(X_train), len(X_test))
    logger.info("Class distribution: %s", dict(zip(*np.unique(y_encoded, return_counts=True))))

    results = {}
    models = {
        "logistic_regression": LogisticRegression(
            max_iter=1000, multi_class="multinomial", random_state=42
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=100, max_depth=4, random_state=42
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=100, max_depth=6, random_state=42
        ),
    }

    for name, model in models.items():
        logger.info("Training %s...", name)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Multi-class AUC
        try:
            if hasattr(model, "predict_proba"):
                y_proba = model.predict_proba(X_test)
                auc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="weighted")
            else:
                auc = None
        except Exception:
            auc = None

        precision, recall, f1, _ = precision_recall_fscore_support(
            y_test, y_pred, average="weighted"
        )

        report = classification_report(
            y_test, y_pred, target_names=le.classes_, output_dict=True
        )

        cm = confusion_matrix(y_test, y_pred)

        # Feature importance
        feature_importance = {}
        if hasattr(model, "feature_importances_"):
            for col, imp in zip(feature_cols, model.feature_importances_):
                feature_importance[col] = float(imp)
        elif hasattr(model, "coef_"):
            for col, coefs in zip(feature_cols, np.abs(model.coef_).mean(axis=0)):
                feature_importance[col] = float(coefs)

        # Sort by importance
        feature_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )

        result = {
            "model_name": name,
            "accuracy": float(accuracy),
            "auc_weighted": float(auc) if auc is not None else None,
            "precision_weighted": float(precision),
            "recall_weighted": float(recall),
            "f1_weighted": float(f1),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "feature_importance": feature_importance,
            "classes": le.classes_.tolist(),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
        }
        results[name] = result

        logger.info(
            "  %s: accuracy=%.3f, f1=%.3f, auc=%s",
            name, accuracy, f1, f"{auc:.3f}" if auc else "N/A"
        )

        # Save model artifact
        model_path = os.path.join(output_dir, f"{name}.joblib")
        joblib.dump(model, model_path)
        logger.info("  Model saved: %s", model_path)

    # Save scaler and label encoder
    joblib.dump(scaler, os.path.join(output_dir, "scaler.joblib"))
    joblib.dump(le, os.path.join(output_dir, "label_encoder.joblib"))

    # Save metadata
    metadata = {
        "trained_at": datetime.utcnow().isoformat(),
        "model_version": "synthetic-v1",
        "data_source": "synthetic",
        "feature_columns": feature_cols,
        "target": "decision",
        "classes": le.classes_.tolist(),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "WARNING": "This model was trained on SYNTHETIC data and is NOT suitable for production underwriting decisions.",
        "models": {
            name: {
                "accuracy": r["accuracy"],
                "f1": r["f1_weighted"],
                "auc": r["auc_weighted"],
            }
            for name, r in results.items()
        },
    }
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    # Save evaluation report
    report_path = os.path.join(output_dir, "evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Evaluation report saved: %s", report_path)

    # Print summary
    print("\n" + "=" * 70)
    print("MODEL TRAINING REPORT")
    print("=" * 70)
    print(f"Data source: SYNTHETIC (not production)")
    print(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")
    print(f"Classes: {le.classes_.tolist()}")
    print()

    for name, r in results.items():
        print(f"\n--- {name} ---")
        print(f"  Accuracy:  {r['accuracy']:.3f}")
        print(f"  F1 (wtd):  {r['f1_weighted']:.3f}")
        if r["auc_weighted"]:
            print(f"  AUC (wtd): {r['auc_weighted']:.3f}")
        print(f"  Top features:")
        for feat, imp in list(r["feature_importance"].items())[:5]:
            print(f"    {feat}: {imp:.4f}")

    print("\n" + "=" * 70)
    print(f"Artifacts saved to: {output_dir}")
    print("WARNING: These models are trained on SYNTHETIC data only.")
    print("=" * 70)

    return results


def load_model(
    model_name: str = "gradient_boosting",
    models_dir: str = "models",
) -> Tuple:
    """Load a trained model and its preprocessing artifacts.

    Returns (model, scaler, label_encoder, metadata).
    """
    model = joblib.load(os.path.join(models_dir, f"{model_name}.joblib"))
    scaler = joblib.load(os.path.join(models_dir, "scaler.joblib"))
    le = joblib.load(os.path.join(models_dir, "label_encoder.joblib"))

    with open(os.path.join(models_dir, "metadata.json")) as f:
        metadata = json.load(f)

    return model, scaler, le, metadata


def predict_claim(
    model, scaler, le, metadata,
    total_billed_cents: int,
    total_allowed_cents: int,
    num_claim_lines: int,
    payer_denial_rate: float,
    provider_claim_volume: int,
    days_since_submission: int,
    has_payer_contract: bool,
    is_medicaid: bool,
    billed_to_allowed_ratio: float = None,
) -> Dict[str, Any]:
    """Make a prediction for a single claim.

    Returns dict with decision, probabilities, and risk score.
    """
    if billed_to_allowed_ratio is None:
        billed_to_allowed_ratio = total_billed_cents / max(total_allowed_cents, 1)

    features = np.array([[
        total_billed_cents, total_allowed_cents, num_claim_lines,
        payer_denial_rate, provider_claim_volume, days_since_submission,
        int(has_payer_contract), int(is_medicaid), billed_to_allowed_ratio,
    ]])

    features_scaled = scaler.transform(features)
    prediction = model.predict(features_scaled)[0]
    probabilities = model.predict_proba(features_scaled)[0]

    decision = le.inverse_transform([prediction])[0]
    prob_dict = {cls: float(prob) for cls, prob in zip(le.classes_, probabilities)}

    # Risk score: probability of DENY + 0.5 * probability of NEEDS_REVIEW
    deny_prob = prob_dict.get("DENY", 0)
    review_prob = prob_dict.get("NEEDS_REVIEW", 0)
    risk_score = deny_prob + 0.5 * review_prob

    return {
        "decision": decision,
        "risk_score": risk_score,
        "probabilities": prob_dict,
        "model_version": metadata.get("model_version", "unknown"),
        "data_source": metadata.get("data_source", "unknown"),
        "warning": "Prediction based on SYNTHETIC training data - not for production use",
    }


def main():
    if not ML_AVAILABLE:
        print("ERROR: ML dependencies not installed.")
        print("Install with: pip install scikit-learn numpy pandas joblib")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Train Spoonbill underwriting models")
    parser.add_argument("--output-dir", default="models", help="Directory for model artifacts")
    parser.add_argument("--practice-id", type=int, help="Filter to specific practice")
    args = parser.parse_args()

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        df = extract_features(db)
        if df.empty:
            logger.error("No training data available. Run generate_synthetic_data.py first.")
            sys.exit(1)

        if args.practice_id:
            df = df[df.get("practice_id") == args.practice_id]
            if df.empty:
                logger.error("No data for practice_id=%d", args.practice_id)
                sys.exit(1)

        results = train_models(df, args.output_dir)

    finally:
        db.close()


if __name__ == "__main__":
    main()
