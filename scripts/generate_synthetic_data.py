#!/usr/bin/env python3
"""Synthetic data generator for Spoonbill ontology objects.

Generates realistic dental claim data across 3 practice archetypes:
1. Small PPO-heavy general dentist
2. Multi-provider high-volume practice
3. Medicaid-heavy / lower reimbursement / higher exception practice

Usage:
    python scripts/generate_synthetic_data.py [--seed 42] [--archetype all|small_ppo|multi_provider|medicaid]

This populates all 10 ontology objects plus supporting tables.
All generated data is clearly marked as synthetic (source_system = 'SYNTHETIC').
"""
import argparse
import logging
import os
import random
import sys
from datetime import date, datetime, timedelta
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.practice import Practice
from app.models.provider import Provider, ProviderRole
from app.models.payer import Payer
from app.models.payer_contract import PayerContract, NetworkStatus, ContractStatus
from app.models.procedure_code import ProcedureCode, ProcedureCategory
from app.models.claim import Claim, ClaimStatus
from app.models.claim_line import ClaimLine, ClaimLineStatus
from app.models.funding_decision import FundingDecision, FundingDecisionType
from app.models.payment import PaymentIntent, PaymentIntentStatus
from app.models.remittance import (
    Remittance, RemittanceLine, PostingStatus,
    RemittanceSourceType, RemittanceLineMatchStatus,
)
from app.models.fee_schedule import FeeScheduleItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── CDT Procedure Code Catalog ───

CDT_CODES = [
    # Preventive
    ("D0120", "Periodic oral evaluation", "PREVENTIVE", 5000, 8500),
    ("D0150", "Comprehensive oral evaluation", "PREVENTIVE", 7500, 12000),
    ("D0210", "Full mouth radiographs", "PREVENTIVE", 10000, 18000),
    ("D0274", "Bitewings - four films", "PREVENTIVE", 5000, 8000),
    ("D1110", "Prophylaxis - adult", "PREVENTIVE", 7500, 12000),
    ("D1120", "Prophylaxis - child", "PREVENTIVE", 5000, 8000),
    ("D1206", "Topical fluoride varnish", "PREVENTIVE", 2500, 4500),
    ("D1351", "Sealant - per tooth", "PREVENTIVE", 3000, 5500),
    # Restorative
    ("D2140", "Amalgam - one surface", "RESTORATIVE", 12000, 20000),
    ("D2150", "Amalgam - two surfaces", "RESTORATIVE", 15000, 25000),
    ("D2330", "Resin composite - one surface, anterior", "RESTORATIVE", 14000, 22000),
    ("D2331", "Resin composite - two surfaces, anterior", "RESTORATIVE", 17000, 28000),
    ("D2391", "Resin composite - one surface, posterior", "RESTORATIVE", 15000, 25000),
    ("D2392", "Resin composite - two surfaces, posterior", "RESTORATIVE", 19000, 30000),
    ("D2740", "Crown - porcelain/ceramic", "RESTORATIVE", 80000, 150000),
    ("D2750", "Crown - porcelain fused to high noble metal", "RESTORATIVE", 90000, 160000),
    # Endodontics
    ("D3310", "Root canal - anterior", "ENDODONTICS", 60000, 100000),
    ("D3320", "Root canal - premolar", "ENDODONTICS", 70000, 120000),
    ("D3330", "Root canal - molar", "ENDODONTICS", 90000, 150000),
    # Periodontics
    ("D4341", "Periodontal scaling/root planing - per quadrant", "PERIODONTICS", 20000, 35000),
    ("D4342", "Periodontal scaling - 1-3 teeth per quadrant", "PERIODONTICS", 15000, 25000),
    ("D4910", "Periodontal maintenance", "PERIODONTICS", 12000, 20000),
    # Oral Surgery
    ("D7140", "Extraction - erupted tooth", "ORAL_SURGERY", 15000, 30000),
    ("D7210", "Surgical extraction - erupted tooth", "ORAL_SURGERY", 25000, 45000),
    ("D7230", "Impacted tooth removal - partial bony", "ORAL_SURGERY", 30000, 55000),
    ("D7240", "Impacted tooth removal - complete bony", "ORAL_SURGERY", 35000, 65000),
    # Prosthodontics
    ("D5110", "Complete denture - maxillary", "PROSTHODONTICS", 100000, 200000),
    ("D5120", "Complete denture - mandibular", "PROSTHODONTICS", 100000, 200000),
    ("D6010", "Implant body", "PROSTHODONTICS", 150000, 300000),
    ("D6058", "Abutment supported porcelain/ceramic crown", "PROSTHODONTICS", 100000, 200000),
]

# ─── Payer Definitions ───

PAYER_DEFS = [
    {"code": "DELTA-PPO", "name": "Delta Dental PPO", "plan_types": ["PPO"], "eft": True, "era": True, "filing_days": 365},
    {"code": "DELTA-PREM", "name": "Delta Dental Premier", "plan_types": ["Premier"], "eft": True, "era": True, "filing_days": 365},
    {"code": "CIGNA-DPPO", "name": "Cigna Dental PPO", "plan_types": ["PPO"], "eft": True, "era": True, "filing_days": 365},
    {"code": "AETNA-DMO", "name": "Aetna Dental DMO", "plan_types": ["HMO", "DMO"], "eft": True, "era": True, "filing_days": 180},
    {"code": "UNITED-PPO", "name": "UnitedHealthcare Dental PPO", "plan_types": ["PPO"], "eft": True, "era": True, "filing_days": 365},
    {"code": "METLIFE-PPO", "name": "MetLife Dental PPO", "plan_types": ["PPO"], "eft": True, "era": True, "filing_days": 365},
    {"code": "GUARDIAN-PPO", "name": "Guardian Dental PPO", "plan_types": ["PPO"], "eft": True, "era": False, "filing_days": 365},
    {"code": "MEDICAID-ST", "name": "State Medicaid Dental", "plan_types": ["Medicaid"], "eft": False, "era": True, "filing_days": 90},
    {"code": "BCBS-PPO", "name": "Blue Cross Blue Shield Dental", "plan_types": ["PPO"], "eft": True, "era": True, "filing_days": 365},
    {"code": "HUMANA-PPO", "name": "Humana Dental PPO", "plan_types": ["PPO"], "eft": True, "era": True, "filing_days": 365},
]

# ─── Practice Archetypes ───

ARCHETYPES = {
    "small_ppo": {
        "name": "Bright Smiles Family Dentistry",
        "legal_name": "Bright Smiles Family Dentistry PLLC",
        "dba_name": "Bright Smiles",
        "ein": "12-3456789",
        "group_npi": "1234567890",
        "city": "Austin", "state": "TX", "zip": "78701",
        "pms_type": "Dentrix",
        "clearinghouse": "Tesia",
        "providers": [
            {"name": "Dr. Sarah Chen", "npi": "1111111111", "specialty": "General Dentistry", "role": "OWNER"},
            {"name": "Maria Lopez RDH", "npi": None, "specialty": "Dental Hygiene", "role": "HYGIENIST"},
        ],
        "payer_weights": {"DELTA-PPO": 0.35, "CIGNA-DPPO": 0.20, "UNITED-PPO": 0.15, "METLIFE-PPO": 0.15, "BCBS-PPO": 0.15},
        "claim_count": 200,
        "denial_rate": 0.06,
        "funding_limit_cents": 50000_00,
        "procedure_weights": {"PREVENTIVE": 0.45, "RESTORATIVE": 0.35, "ENDODONTICS": 0.05, "PERIODONTICS": 0.08, "ORAL_SURGERY": 0.05, "PROSTHODONTICS": 0.02},
    },
    "multi_provider": {
        "name": "Metro Dental Group",
        "legal_name": "Metro Dental Group PC",
        "dba_name": "Metro Dental",
        "ein": "98-7654321",
        "group_npi": "2222222222",
        "city": "Chicago", "state": "IL", "zip": "60601",
        "pms_type": "Open Dental",
        "clearinghouse": "DentalXChange",
        "providers": [
            {"name": "Dr. James Wilson", "npi": "2111111111", "specialty": "General Dentistry", "role": "OWNER"},
            {"name": "Dr. Priya Patel", "npi": "2222222222", "specialty": "General Dentistry", "role": "ASSOCIATE"},
            {"name": "Dr. Robert Kim", "npi": "2333333333", "specialty": "Endodontics", "role": "SPECIALIST"},
            {"name": "Lisa Thompson RDH", "npi": None, "specialty": "Dental Hygiene", "role": "HYGIENIST"},
            {"name": "Amy Garcia RDH", "npi": None, "specialty": "Dental Hygiene", "role": "HYGIENIST"},
        ],
        "payer_weights": {"DELTA-PPO": 0.25, "DELTA-PREM": 0.10, "CIGNA-DPPO": 0.15, "AETNA-DMO": 0.10, "UNITED-PPO": 0.15, "METLIFE-PPO": 0.10, "GUARDIAN-PPO": 0.05, "BCBS-PPO": 0.10},
        "claim_count": 600,
        "denial_rate": 0.08,
        "funding_limit_cents": 200000_00,
        "procedure_weights": {"PREVENTIVE": 0.35, "RESTORATIVE": 0.30, "ENDODONTICS": 0.10, "PERIODONTICS": 0.10, "ORAL_SURGERY": 0.08, "PROSTHODONTICS": 0.07},
    },
    "medicaid": {
        "name": "Community Dental Care",
        "legal_name": "Community Dental Care Inc",
        "dba_name": "Community Dental",
        "ein": "55-1234567",
        "group_npi": "3333333333",
        "city": "Memphis", "state": "TN", "zip": "38103",
        "pms_type": "Eaglesoft",
        "clearinghouse": "Availity",
        "providers": [
            {"name": "Dr. Maria Santos", "npi": "3111111111", "specialty": "General Dentistry", "role": "OWNER"},
            {"name": "Dr. David Brown", "npi": "3222222222", "specialty": "General Dentistry", "role": "ASSOCIATE"},
            {"name": "Jennifer White RDH", "npi": None, "specialty": "Dental Hygiene", "role": "HYGIENIST"},
        ],
        "payer_weights": {"MEDICAID-ST": 0.45, "DELTA-PPO": 0.15, "CIGNA-DPPO": 0.10, "HUMANA-PPO": 0.10, "BCBS-PPO": 0.10, "UNITED-PPO": 0.10},
        "claim_count": 400,
        "denial_rate": 0.15,
        "funding_limit_cents": 100000_00,
        "procedure_weights": {"PREVENTIVE": 0.40, "RESTORATIVE": 0.30, "ENDODONTICS": 0.05, "PERIODONTICS": 0.10, "ORAL_SURGERY": 0.10, "PROSTHODONTICS": 0.05},
    },
}

TEETH = [str(i) for i in range(1, 33)]
SURFACES = ["M", "O", "D", "B", "L", "MO", "DO", "MOD", "BOL"]
DENIAL_REASONS = [
    "Missing pre-authorization",
    "Frequency limitation exceeded",
    "Not covered under plan",
    "Missing documentation",
    "Patient not eligible on date of service",
    "Duplicate claim",
    "Timely filing limit exceeded",
    "Coordination of benefits required",
    "Maximum benefit reached",
    "Waiting period not met",
]


def ensure_payers(db: Session) -> dict:
    """Create or get payers, return {code: payer} mapping."""
    payer_map = {}
    for pd in PAYER_DEFS:
        existing = db.query(Payer).filter(Payer.payer_code == pd["code"]).first()
        if existing:
            payer_map[pd["code"]] = existing
        else:
            payer = Payer(
                payer_code=pd["code"],
                name=pd["name"],
                plan_types=pd["plan_types"],
                eft_capable=pd["eft"],
                era_capable=pd["era"],
                filing_limit_days=pd["filing_days"],
            )
            db.add(payer)
            db.flush()
            payer_map[pd["code"]] = payer
    return payer_map


def ensure_procedure_codes(db: Session) -> dict:
    """Create or get procedure codes, return {cdt_code: ProcedureCode} mapping."""
    code_map = {}
    for cdt_code, desc, category, _low, _high in CDT_CODES:
        existing = db.query(ProcedureCode).filter(ProcedureCode.cdt_code == cdt_code).first()
        if existing:
            code_map[cdt_code] = existing
        else:
            pc = ProcedureCode(
                cdt_code=cdt_code,
                short_description=desc,
                category=category,
                common_denial_reasons=random.sample(DENIAL_REASONS, k=min(3, len(DENIAL_REASONS))),
            )
            db.add(pc)
            db.flush()
            code_map[cdt_code] = pc
    return code_map


def weighted_choice(weights: dict, rng: random.Random) -> str:
    """Weighted random selection from {key: weight} dict."""
    items = list(weights.items())
    total = sum(w for _, w in items)
    r = rng.random() * total
    cumulative = 0
    for k, w in items:
        cumulative += w
        if r <= cumulative:
            return k
    return items[-1][0]


def generate_practice(
    db: Session,
    archetype_key: str,
    payer_map: dict,
    code_map: dict,
    rng: random.Random,
) -> dict:
    """Generate a complete practice with all ontology objects."""
    arch = ARCHETYPES[archetype_key]
    logger.info("Generating practice: %s (%s)", arch["name"], archetype_key)

    # 1. Practice
    practice = Practice(
        name=arch["name"],
        legal_name=arch["legal_name"],
        dba_name=arch["dba_name"],
        ein=arch["ein"],
        group_npi=arch["group_npi"],
        address_line1=f"{rng.randint(100, 9999)} Main Street",
        city=arch["city"],
        state=arch["state"],
        zip_code=arch["zip"],
        pms_type=arch["pms_type"],
        clearinghouse=arch["clearinghouse"],
        status="active",
        funding_limit_cents=arch["funding_limit_cents"],
    )
    db.add(practice)
    db.flush()
    logger.info("  Practice created: id=%d", practice.id)

    # 2. Providers
    providers = []
    for pdef in arch["providers"]:
        provider = Provider(
            practice_id=practice.id,
            full_name=pdef["name"],
            npi=pdef["npi"],
            specialty=pdef["specialty"],
            role=pdef["role"],
            is_active=True,
        )
        db.add(provider)
        db.flush()
        providers.append(provider)
    logger.info("  %d providers created", len(providers))

    # 3. Payer Contracts
    contracts = {}
    for payer_code in arch["payer_weights"].keys():
        payer = payer_map.get(payer_code)
        if not payer:
            continue
        contract = PayerContract(
            practice_id=practice.id,
            payer_id=payer.id,
            effective_start_date=date(2024, 1, 1),
            effective_end_date=date(2026, 12, 31),
            network_status=NetworkStatus.IN_NETWORK.value if payer_code != "MEDICAID-ST" else NetworkStatus.OUT_OF_NETWORK.value,
            status=ContractStatus.ACTIVE.value,
            timely_filing_limit_days=payer.filing_limit_days,
        )
        db.add(contract)
        db.flush()
        contracts[payer_code] = contract

        # FeeScheduleItems for this contract
        for cdt_code, _desc, _cat, low, high in CDT_CODES:
            pc = code_map.get(cdt_code)
            if not pc:
                continue
            # Medicaid pays less
            if "Medicaid" in (payer.plan_types or []):
                allowed = int(low * rng.uniform(0.4, 0.7))
            else:
                allowed = int(rng.uniform(low * 0.7, high * 0.9))
            fsi = FeeScheduleItem(
                payer_contract_id=contract.id,
                procedure_code_id=pc.id,
                cdt_code=cdt_code,
                allowed_amount_cents=allowed,
            )
            db.add(fsi)

    db.flush()
    logger.info("  %d payer contracts created with fee schedules", len(contracts))

    # 4. Claims + ClaimLines + FundingDecisions + PaymentIntents
    claim_count = arch["claim_count"]
    today = date.today()
    claims = []
    funding_decisions = []
    payment_intents = []

    # Separate providers for claim assignment
    billing_providers = [p for p in providers if p.role in ("OWNER", "ASSOCIATE", "SPECIALIST")]
    if not billing_providers:
        billing_providers = providers

    for i in range(claim_count):
        # Pick payer
        payer_code = weighted_choice(arch["payer_weights"], rng)
        payer = payer_map.get(payer_code)
        contract = contracts.get(payer_code)

        # Pick provider
        provider = rng.choice(billing_providers)

        # Date of service: spread across last 180 days
        dos = today - timedelta(days=rng.randint(1, 180))

        # Pick procedures (1-4 per claim)
        num_lines = rng.choices([1, 2, 3, 4], weights=[0.35, 0.35, 0.20, 0.10])[0]
        category = weighted_choice(arch["procedure_weights"], rng)
        eligible_codes = [c for c in CDT_CODES if c[2] == category]
        if not eligible_codes:
            eligible_codes = CDT_CODES[:8]

        selected_codes = rng.choices(eligible_codes, k=num_lines)

        total_billed = 0
        total_allowed = 0
        line_data = []
        for cdt_code, _desc, _cat, low, high in selected_codes:
            billed = rng.randint(low, high)
            allowed = int(billed * rng.uniform(0.5, 0.95))
            total_billed += billed
            total_allowed += allowed
            line_data.append((cdt_code, billed, allowed))

        # Determine claim status
        is_denied = rng.random() < arch["denial_rate"]
        days_since_dos = (today - dos).days

        if is_denied:
            status = ClaimStatus.DECLINED.value
        elif days_since_dos < 14:
            status = rng.choice([ClaimStatus.SUBMITTED.value, ClaimStatus.PENDING.value])
        elif days_since_dos < 45:
            status = rng.choice([ClaimStatus.PENDING.value, ClaimStatus.APPROVED.value, ClaimStatus.APPROVED.value])
        else:
            status = rng.choice([ClaimStatus.APPROVED.value, ClaimStatus.APPROVED.value, ClaimStatus.PAID.value])

        # Submission date
        submitted_at = datetime.combine(dos + timedelta(days=rng.randint(0, 3)), datetime.min.time())
        adjudicated_at = None
        if status in (ClaimStatus.APPROVED.value, ClaimStatus.DECLINED.value, ClaimStatus.PAID.value):
            adjudicated_at = submitted_at + timedelta(days=rng.randint(7, 60))

        total_paid = 0
        if status == ClaimStatus.PAID.value:
            total_paid = int(total_allowed * rng.uniform(0.85, 1.0))
        elif status == ClaimStatus.APPROVED.value and rng.random() > 0.5:
            total_paid = int(total_allowed * rng.uniform(0.85, 1.0))

        external_claim_id = f"SYN-{archetype_key[:3].upper()}-{i+1:05d}"

        claim = Claim(
            practice_id=practice.id,
            payer_id=payer.id if payer else None,
            provider_id=provider.id,
            payer_contract_id=contract.id if contract else None,
            external_claim_id=external_claim_id,
            payer_name=payer.name if payer else "Unknown",
            patient_name=f"Patient {rng.randint(1000, 9999)}",
            date_of_service=dos,
            status=status,
            amount_cents=total_billed,
            total_billed_cents=total_billed,
            total_allowed_cents=total_allowed,
            total_paid_cents=total_paid if total_paid > 0 else None,
            submitted_at=submitted_at,
            adjudicated_at=adjudicated_at,
            source_system="SYNTHETIC",
        )
        db.add(claim)
        db.flush()
        claims.append(claim)

        # ClaimLines
        for cdt_code, billed, allowed in line_data:
            pc = code_map.get(cdt_code)
            line_status = ClaimLineStatus.PAID.value if status == ClaimStatus.PAID.value else (
                ClaimLineStatus.DENIED.value if is_denied else ClaimLineStatus.PENDING.value
            )
            cl = ClaimLine(
                claim_id=claim.id,
                procedure_code_id=pc.id if pc else None,
                provider_id=provider.id,
                cdt_code=cdt_code,
                tooth=rng.choice(TEETH) if rng.random() > 0.3 else None,
                surface=rng.choice(SURFACES) if rng.random() > 0.5 else None,
                billed_fee_cents=billed,
                allowed_fee_cents=allowed,
                units=1,
                line_status=line_status,
            )
            db.add(cl)

        # FundingDecision
        if status in (ClaimStatus.APPROVED.value, ClaimStatus.PAID.value):
            risk_score = rng.uniform(0.05, 0.35)
            fd = FundingDecision(
                claim_id=claim.id,
                decision=FundingDecisionType.APPROVE.value,
                advance_rate=rng.uniform(0.70, 0.90),
                max_advance_amount_cents=int(total_billed * 0.80),
                fee_rate=rng.uniform(0.02, 0.05),
                risk_score=risk_score,
                reasons_json=[{"rule": "auto_approve", "detail": "Synthetic data - auto approved"}],
                decisioned_at=submitted_at + timedelta(minutes=rng.randint(5, 120)),
                model_version="synthetic-v1",
                policy_version="policy-v1",
            )
            db.add(fd)
            db.flush()
            funding_decisions.append(fd)

            # PaymentIntent for approved claims
            pi = PaymentIntent(
                claim_id=claim.id,
                practice_id=practice.id,
                amount_cents=fd.max_advance_amount_cents,
                status=PaymentIntentStatus.CONFIRMED.value if status == ClaimStatus.PAID.value else PaymentIntentStatus.QUEUED.value,
                queued_at=fd.decisioned_at + timedelta(minutes=5),
            )
            pi.idempotency_key = pi.generate_idempotency_key()
            if status == ClaimStatus.PAID.value:
                pi.sent_at = pi.queued_at + timedelta(hours=rng.randint(1, 24))
                pi.confirmed_at = pi.sent_at + timedelta(hours=rng.randint(1, 48))
            db.add(pi)
            db.flush()
            payment_intents.append(pi)

        elif is_denied:
            risk_score = rng.uniform(0.5, 0.95)
            fd = FundingDecision(
                claim_id=claim.id,
                decision=FundingDecisionType.DENY.value,
                risk_score=risk_score,
                reasons_json=[{"rule": "high_risk_score", "detail": f"Risk score {risk_score:.3f} - synthetic denial"}],
                decisioned_at=submitted_at + timedelta(minutes=rng.randint(5, 60)),
                model_version="synthetic-v1",
                policy_version="policy-v1",
            )
            db.add(fd)
            db.flush()
            funding_decisions.append(fd)

    db.flush()
    logger.info("  %d claims, %d funding decisions, %d payment intents created",
                len(claims), len(funding_decisions), len(payment_intents))

    # 5. Remittances + RemittanceLines
    # Group paid claims by payer for remittance batches
    paid_claims = [c for c in claims if c.total_paid_cents and c.total_paid_cents > 0]
    remittances = []

    # Create remittance batches by payer
    payer_groups = {}
    for c in paid_claims:
        key = c.payer_name or "Unknown"
        payer_groups.setdefault(key, []).append(c)

    for payer_name, payer_claims in payer_groups.items():
        # Split into batches of 5-20 claims
        batch_size = rng.randint(5, min(20, len(payer_claims)))
        for batch_start in range(0, len(payer_claims), batch_size):
            batch = payer_claims[batch_start:batch_start + batch_size]
            if not batch:
                continue

            total_paid = sum(c.total_paid_cents for c in batch)
            total_adj = int(total_paid * rng.uniform(0.01, 0.08))

            payment_date = max(c.adjudicated_at for c in batch if c.adjudicated_at) + timedelta(days=rng.randint(3, 14))

            rem = Remittance(
                practice_id=practice.id,
                payer_id=batch[0].payer_id,
                payer_name=payer_name,
                trace_number=f"TRC-{rng.randint(100000, 999999)}",
                payment_date=payment_date.date() if isinstance(payment_date, datetime) else payment_date,
                total_paid_cents=total_paid,
                total_adjustments_cents=total_adj,
                posting_status=PostingStatus.POSTED.value,
                source_type=RemittanceSourceType.SYNTHETIC.value,
            )
            db.add(rem)
            db.flush()
            remittances.append(rem)

            for c in batch:
                # Most lines match, some don't
                match_roll = rng.random()
                if match_roll < 0.85:
                    match_status = RemittanceLineMatchStatus.MATCHED.value
                elif match_roll < 0.95:
                    match_status = RemittanceLineMatchStatus.UNMATCHED.value
                else:
                    match_status = RemittanceLineMatchStatus.MISMATCH.value

                rl = RemittanceLine(
                    remittance_id=rem.id,
                    claim_id=c.id,
                    external_claim_id=c.external_claim_id,
                    paid_cents=c.total_paid_cents,
                    allowed_cents=c.total_allowed_cents,
                    adjustment_cents=int(c.total_paid_cents * rng.uniform(0.0, 0.05)),
                    match_status=match_status,
                )
                db.add(rl)

    db.flush()
    logger.info("  %d remittances created", len(remittances))

    stats = {
        "practice_id": practice.id,
        "archetype": archetype_key,
        "providers": len(providers),
        "contracts": len(contracts),
        "claims": len(claims),
        "funding_decisions": len(funding_decisions),
        "payment_intents": len(payment_intents),
        "remittances": len(remittances),
    }
    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Spoonbill data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument("--archetype", choices=["all", "small_ppo", "multi_provider", "medicaid"], default="all",
                        help="Which practice archetype(s) to generate")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    random.seed(args.seed)

    db = SessionLocal()
    try:
        # Shared reference data
        payer_map = ensure_payers(db)
        code_map = ensure_procedure_codes(db)
        db.flush()

        archetypes_to_gen = list(ARCHETYPES.keys()) if args.archetype == "all" else [args.archetype]

        all_stats = []
        for arch_key in archetypes_to_gen:
            stats = generate_practice(db, arch_key, payer_map, code_map, rng)
            all_stats.append(stats)

        db.commit()
        logger.info("=" * 60)
        logger.info("Synthetic data generation complete!")
        for s in all_stats:
            logger.info(
                "  %s (id=%d): %d providers, %d contracts, %d claims, %d decisions, %d payments, %d remittances",
                s["archetype"], s["practice_id"], s["providers"], s["contracts"],
                s["claims"], s["funding_decisions"], s["payment_intents"], s["remittances"],
            )
        logger.info("=" * 60)

    except Exception:
        db.rollback()
        logger.exception("Synthetic data generation failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
