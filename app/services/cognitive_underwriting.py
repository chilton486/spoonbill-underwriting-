"""Cognitive underwriting integration service.

Two-layer underwriting pipeline:
  Layer 1: Deterministic rules (existing UnderwritingService + FundingDecisionService)
  Layer 2: Cognitive augmentation via Anthropic (this module)

Decision policy:
- Hard fail conditions remain deterministic (duplicates, missing fields, thresholds)
- If deterministic says APPROVE but model finds elevated ambiguity -> NEEDS_REVIEW
- If deterministic says NEEDS_REVIEW, model can enrich but not auto-approve
- If model is unavailable, system falls back cleanly to deterministic only
- Model never directly triggers money movement
"""
import json
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.claim import Claim
from ..models.practice import Practice
from ..models.underwriting_run import UnderwritingRun
from ..schemas.cognitive import (
    UnderwriteClaimInput,
    UnderwriteClaimOutput,
    CognitiveRecommendation,
    PracticeContext,
    PayerContext,
    PayerContractContext,
    ProviderContext,
    ClaimLineContext,
    DeterministicSignals,
    ParseEobInput,
    ParseEobOutput,
    OntologyUpdateInput,
    OntologyUpdateOutput,
)
from ..services.anthropic_service import AnthropicService, AnthropicServiceError

logger = logging.getLogger(__name__)
settings = get_settings()


class CognitiveUnderwritingService:
    """Orchestrates the two-layer underwriting pipeline."""

    @staticmethod
    def is_cognitive_enabled() -> bool:
        """Check if cognitive underwriting is enabled and available."""
        return (
            settings.cognitive_underwriting_enabled
            and AnthropicService.is_available()
        )

    @staticmethod
    def build_claim_context(
        db: Session,
        claim: Claim,
        deterministic_decision: str,
        deterministic_reasons: list,
    ) -> UnderwriteClaimInput:
        """Build the full context object for cognitive underwriting.

        Gathers practice, payer, contract, provider, and claim line context
        from the database to provide rich input to the model.
        """
        # Practice context
        practice = db.query(Practice).filter(Practice.id == claim.practice_id).first()
        practice_ctx = PracticeContext(
            id=claim.practice_id,
            name=practice.name if practice else "Unknown",
            status=practice.status if practice else None,
            pms_type=getattr(practice, "pms_type", None) if practice else None,
            clearinghouse=getattr(practice, "clearinghouse", None) if practice else None,
            state=getattr(practice, "state", None) if practice else None,
        )

        # Payer context
        payer_name = claim.payer or "Unknown"
        payer_ctx = PayerContext(name=payer_name)

        if claim.payer_id:
            try:
                from ..models.payer import Payer
                payer_obj = db.query(Payer).filter(Payer.id == claim.payer_id).first()
                if payer_obj:
                    payer_ctx = PayerContext(
                        id=payer_obj.id,
                        name=payer_obj.name,
                        plan_types=payer_obj.plan_types if hasattr(payer_obj, "plan_types") else None,
                        eft_capable=payer_obj.eft_capable if hasattr(payer_obj, "eft_capable") else None,
                        era_capable=payer_obj.era_capable if hasattr(payer_obj, "era_capable") else None,
                        filing_limit_days=payer_obj.filing_limit_days if hasattr(payer_obj, "filing_limit_days") else None,
                    )
            except Exception:
                pass

        # Payer contract context
        contract_ctx = None
        if claim.payer_contract_id:
            try:
                from ..models.payer_contract import PayerContract
                contract = db.query(PayerContract).filter(
                    PayerContract.id == claim.payer_contract_id
                ).first()
                if contract:
                    contract_ctx = PayerContractContext(
                        id=contract.id,
                        network_status=contract.network_status if hasattr(contract, "network_status") else None,
                        status=contract.status if hasattr(contract, "status") else None,
                        timely_filing_limit_days=contract.timely_filing_limit_days if hasattr(contract, "timely_filing_limit_days") else None,
                    )
            except Exception:
                pass

        # Provider context
        provider_ctx = None
        if claim.provider_id:
            try:
                from ..models.provider import Provider
                provider = db.query(Provider).filter(
                    Provider.id == claim.provider_id
                ).first()
                if provider:
                    provider_ctx = ProviderContext(
                        id=provider.id,
                        full_name=provider.full_name,
                        npi=provider.npi if hasattr(provider, "npi") else None,
                        specialty=provider.specialty if hasattr(provider, "specialty") else None,
                        role=provider.role if hasattr(provider, "role") else None,
                    )
            except Exception:
                pass

        # Claim lines
        claim_lines_ctx = []
        if hasattr(claim, "claim_lines") and claim.claim_lines:
            for cl in claim.claim_lines:
                line_ctx = ClaimLineContext(
                    billed_fee_cents=cl.billed_fee_cents or 0,
                    units=cl.units or 1,
                    tooth=cl.tooth if hasattr(cl, "tooth") else None,
                    surface=cl.surface if hasattr(cl, "surface") else None,
                )
                if cl.procedure_code_id:
                    try:
                        from ..models.procedure_code import ProcedureCode
                        pc = db.query(ProcedureCode).filter(
                            ProcedureCode.id == cl.procedure_code_id
                        ).first()
                        if pc:
                            line_ctx.cdt_code = pc.cdt_code
                            line_ctx.description = pc.short_description
                            line_ctx.category = pc.category
                            line_ctx.risk_notes = pc.risk_notes if hasattr(pc, "risk_notes") else None
                    except Exception:
                        pass
                claim_lines_ctx.append(line_ctx)

        # Build deterministic signals
        det_reasons = []
        for r in deterministic_reasons:
            if isinstance(r, dict):
                det_reasons.append(r)
            else:
                det_reasons.append({"rule": str(r), "detail": str(r)})

        deterministic = DeterministicSignals(
            decision=deterministic_decision,
            reasons=det_reasons,
            duplicate_detected=any(
                (isinstance(r, str) and "DUPLICATE" in r) or
                (isinstance(r, dict) and "duplicate" in r.get("rule", "").lower())
                for r in deterministic_reasons
            ),
            missing_required_fields=[
                r for r in deterministic_reasons
                if isinstance(r, str) and "MISSING" in r
            ],
            amount_exceeds_threshold=any(
                (isinstance(r, str) and "THRESHOLD" in r) or
                (isinstance(r, dict) and "threshold" in r.get("rule", "").lower())
                for r in deterministic_reasons
            ),
        )

        billed = claim.total_billed_cents or claim.amount_cents or 0
        claim_age = None
        if claim.procedure_date:
            claim_age = (datetime.utcnow().date() - claim.procedure_date).days

        return UnderwriteClaimInput(
            claim_id=claim.id,
            claim_token=claim.claim_token,
            external_claim_id=claim.external_claim_id,
            practice=practice_ctx,
            payer=payer_ctx,
            payer_contract=contract_ctx,
            provider=provider_ctx,
            claim_lines=claim_lines_ctx,
            total_billed_cents=billed,
            total_allowed_cents=claim.total_allowed_cents,
            patient_responsibility_estimate=claim.patient_responsibility_estimate,
            procedure_date=claim.procedure_date.isoformat() if claim.procedure_date else None,
            submitted_at=claim.submitted_at.isoformat() if claim.submitted_at else None,
            claim_age_days=claim_age,
            deterministic=deterministic,
        )

    @staticmethod
    def merge_decisions(
        deterministic_decision: str,
        cognitive_output: Optional[UnderwriteClaimOutput],
    ) -> str:
        """Merge deterministic and cognitive recommendations.

        Policy:
        - If deterministic is DECLINE -> always DECLINE (hard block)
        - If deterministic is APPROVE + model says NEEDS_REVIEW -> NEEDS_REVIEW
        - If deterministic is APPROVE + model says DECLINE -> NEEDS_REVIEW (escalate, don't auto-decline)
        - If deterministic is NEEDS_REVIEW + model says APPROVE -> stay NEEDS_REVIEW (model can't auto-approve)
        - If model unavailable -> use deterministic as-is
        """
        if cognitive_output is None:
            return deterministic_decision

        model_rec = cognitive_output.recommendation.value

        # Deterministic hard blocks are final
        if deterministic_decision == "DECLINE":
            return "DECLINE"

        # Deterministic APPROVE
        if deterministic_decision == "APPROVE":
            if model_rec == "DECLINE":
                # Model says decline but deterministic approved - escalate to review
                return "NEEDS_REVIEW"
            elif model_rec == "NEEDS_REVIEW":
                return "NEEDS_REVIEW"
            else:
                return "APPROVE"

        # Deterministic NEEDS_REVIEW
        if deterministic_decision == "NEEDS_REVIEW":
            # Model cannot auto-approve out of NEEDS_REVIEW
            if model_rec == "DECLINE":
                return "DECLINE"
            return "NEEDS_REVIEW"

        return deterministic_decision

    @staticmethod
    def run_cognitive_layer(
        db: Session,
        claim: Claim,
        deterministic_decision: str,
        deterministic_reasons: list,
        user_id: Optional[int] = None,
    ) -> Tuple[Optional[UnderwriteClaimOutput], Optional[UnderwritingRun]]:
        """Run the cognitive underwriting layer.

        Returns (cognitive_output, underwriting_run) or (None, run_with_fallback_info)
        if cognitive layer fails.
        """
        if not CognitiveUnderwritingService.is_cognitive_enabled():
            return None, None

        # Build context
        try:
            input_data = CognitiveUnderwritingService.build_claim_context(
                db, claim, deterministic_decision, deterministic_reasons
            )
        except Exception as e:
            logger.error("Failed to build cognitive context for claim %s: %s", claim.id, e)
            run = UnderwritingRun(
                claim_id=claim.id,
                practice_id=claim.practice_id,
                model_provider="anthropic",
                model_name=settings.anthropic_model,
                prompt_version=settings.anthropic_prompt_version,
                run_type="underwrite_claim",
                fallback_used=True,
                fallback_reason=f"Context build failed: {str(e)}",
                parse_success=False,
                error_message=str(e),
                deterministic_recommendation=deterministic_decision,
                merged_recommendation=deterministic_decision,
            )
            db.add(run)
            return None, run

        # Call Anthropic
        try:
            output, metadata = AnthropicService.underwrite_claim(input_data)
        except AnthropicServiceError as e:
            logger.warning(
                "Cognitive underwriting failed for claim %s, falling back: %s",
                claim.id, e,
            )
            run = UnderwritingRun(
                claim_id=claim.id,
                practice_id=claim.practice_id,
                model_provider="anthropic",
                model_name=settings.anthropic_model,
                prompt_version=settings.anthropic_prompt_version,
                input_hash=AnthropicService._compute_input_hash(
                    input_data.model_dump(mode="json")
                ),
                run_type="underwrite_claim",
                fallback_used=True,
                fallback_reason=str(e),
                parse_success=False,
                error_message=str(e),
                deterministic_recommendation=deterministic_decision,
                merged_recommendation=deterministic_decision,
            )
            db.add(run)
            return None, run

        # Merge decisions
        merged = CognitiveUnderwritingService.merge_decisions(
            deterministic_decision, output
        )

        # Persist the run
        run = UnderwritingRun(
            claim_id=claim.id,
            practice_id=claim.practice_id,
            model_provider="anthropic",
            model_name=metadata["model_name"],
            prompt_version=metadata["prompt_version"],
            input_hash=metadata["input_hash"],
            output_json=metadata["raw_output"],
            recommendation=output.recommendation.value,
            risk_score=output.risk_score,
            confidence_score=output.confidence_score,
            run_type="underwrite_claim",
            latency_ms=metadata["latency_ms"],
            fallback_used=False,
            parse_success=True,
            deterministic_recommendation=deterministic_decision,
            merged_recommendation=merged,
        )
        db.add(run)

        return output, run

    @staticmethod
    def run_eob_parsing(
        db: Session,
        input_data: ParseEobInput,
        practice_id: int,
        claim_id: Optional[int] = None,
    ) -> Tuple[Optional[ParseEobOutput], Optional[UnderwritingRun]]:
        """Run cognitive EOB parsing.

        Returns (parsed_output, underwriting_run) or (None, run_with_error).
        """
        if not settings.cognitive_eob_parsing_enabled or not AnthropicService.is_available():
            return None, None

        try:
            output, metadata = AnthropicService.parse_eob(input_data)
        except AnthropicServiceError as e:
            logger.warning("EOB parsing failed: %s", e)
            run = UnderwritingRun(
                claim_id=claim_id,
                practice_id=practice_id,
                model_provider="anthropic",
                model_name=settings.anthropic_model,
                prompt_version=settings.anthropic_prompt_version,
                run_type="parse_eob",
                fallback_used=True,
                fallback_reason=str(e),
                parse_success=False,
                error_message=str(e),
            )
            db.add(run)
            return None, run

        run = UnderwritingRun(
            claim_id=claim_id,
            practice_id=practice_id,
            model_provider="anthropic",
            model_name=metadata["model_name"],
            prompt_version=metadata["prompt_version"],
            input_hash=metadata["input_hash"],
            output_json=metadata["raw_output"],
            run_type="parse_eob",
            latency_ms=metadata["latency_ms"],
            fallback_used=False,
            parse_success=True,
        )
        db.add(run)
        return output, run

    @staticmethod
    def run_ontology_updates(
        db: Session,
        input_data: OntologyUpdateInput,
        claim_id: Optional[int] = None,
    ) -> Tuple[Optional[OntologyUpdateOutput], Optional[UnderwritingRun]]:
        """Run cognitive ontology update generation.

        Returns (update_output, underwriting_run) or (None, run_with_error).
        """
        if not settings.cognitive_ontology_updates_enabled or not AnthropicService.is_available():
            return None, None

        try:
            output, metadata = AnthropicService.generate_ontology_updates(input_data)
        except AnthropicServiceError as e:
            logger.warning("Ontology update generation failed: %s", e)
            run = UnderwritingRun(
                claim_id=claim_id,
                practice_id=input_data.practice_id,
                model_provider="anthropic",
                model_name=settings.anthropic_model,
                prompt_version=settings.anthropic_prompt_version,
                run_type="ontology_updates",
                fallback_used=True,
                fallback_reason=str(e),
                parse_success=False,
                error_message=str(e),
            )
            db.add(run)
            return None, run

        run = UnderwritingRun(
            claim_id=claim_id,
            practice_id=input_data.practice_id,
            model_provider="anthropic",
            model_name=metadata["model_name"],
            prompt_version=metadata["prompt_version"],
            input_hash=metadata["input_hash"],
            output_json=metadata["raw_output"],
            run_type="ontology_updates",
            latency_ms=metadata["latency_ms"],
            fallback_used=False,
            parse_success=True,
        )
        db.add(run)
        return output, run
