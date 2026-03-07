"""Anthropic cognitive underwriting service.

Wraps the Anthropic Python SDK in a clean, testable abstraction.
Provides three core capabilities:
1. underwrite_claim() - Cognitive claim evaluation
2. parse_eob() - EOB/ERA text parsing
3. generate_ontology_updates() - Ontology update proposals

All calls produce structured, validated outputs via Pydantic schemas.
Falls back gracefully if Anthropic is unavailable or returns invalid output.
"""
import hashlib
import json
import logging
import time
from typing import Optional, Tuple

from ..config import get_settings
from ..schemas.cognitive import (
    UnderwriteClaimInput,
    UnderwriteClaimOutput,
    CognitiveRecommendation,
    ParseEobInput,
    ParseEobOutput,
    ReconciliationAction,
    OntologyUpdateInput,
    OntologyUpdateOutput,
    RiskFactor,
    PolicyFlag,
    OntologyObservation,
    NextAction,
    EobClaimMatch,
    EobLineAdjudication,
    EntityUpdate,
    KPIUpdate,
    RiskFlag,
    BehaviorObservation,
)
from ..prompts.underwriting_v1 import (
    SYSTEM_PROMPT as UW_SYSTEM_PROMPT,
    VERSION as UW_VERSION,
    format_user_prompt as format_uw_prompt,
)
from ..prompts.eob_parsing_v1 import (
    SYSTEM_PROMPT as EOB_SYSTEM_PROMPT,
    VERSION as EOB_VERSION,
    format_user_prompt as format_eob_prompt,
)
from ..prompts.ontology_updates_v1 import (
    SYSTEM_PROMPT as ONTO_SYSTEM_PROMPT,
    VERSION as ONTO_VERSION,
    format_user_prompt as format_onto_prompt,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class AnthropicServiceError(Exception):
    """Raised when the Anthropic service encounters an error."""
    pass


class AnthropicService:
    """Centralized Anthropic SDK wrapper for cognitive underwriting.

    All Anthropic API interactions go through this service.
    Responses are always validated against Pydantic schemas.
    """

    _client = None

    @classmethod
    def _get_client(cls):
        """Lazy-initialize the Anthropic client."""
        if cls._client is None:
            if not settings.anthropic_api_key:
                raise AnthropicServiceError(
                    "ANTHROPIC_API_KEY not configured. "
                    "Set it in .env or environment variables."
                )
            try:
                import anthropic
                cls._client = anthropic.Anthropic(
                    api_key=settings.anthropic_api_key,
                    timeout=settings.anthropic_timeout_seconds,
                    max_retries=settings.anthropic_max_retries,
                )
            except ImportError:
                raise AnthropicServiceError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return cls._client

    @classmethod
    def is_available(cls) -> bool:
        """Check if the Anthropic service is enabled and configured."""
        return (
            settings.anthropic_enabled
            and bool(settings.anthropic_api_key)
        )

    @staticmethod
    def _compute_input_hash(data: dict) -> str:
        """Compute a SHA-256 hash of the input for audit trail."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @classmethod
    def _call_anthropic(
        cls,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[str, int]:
        """Make a raw Anthropic API call and return (response_text, latency_ms).

        Raises AnthropicServiceError on failure.
        """
        client = cls._get_client()
        start = time.monotonic()
        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            # Extract text from response
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text
            if not text_content:
                raise AnthropicServiceError("Empty response from Anthropic")
            return text_content, latency_ms
        except AnthropicServiceError:
            raise
        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "Anthropic API call failed after %dms: %s", latency_ms, str(e)
            )
            raise AnthropicServiceError(f"Anthropic API error: {str(e)}")

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse JSON from model response, handling markdown code blocks."""
        cleaned = text.strip()
        # Strip markdown code block if present
        if cleaned.startswith("```"):
            # Remove opening ```json or ```
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise AnthropicServiceError(f"Invalid JSON in response: {e}")

    # ── underwrite_claim ───────────────────────────────────────────────

    @classmethod
    def underwrite_claim(
        cls, input_data: UnderwriteClaimInput
    ) -> Tuple[UnderwriteClaimOutput, dict]:
        """Run cognitive underwriting on a claim.

        Args:
            input_data: Structured claim context

        Returns:
            Tuple of (validated output, metadata dict with latency/hash/etc.)

        Raises:
            AnthropicServiceError: On API or parsing failure
        """
        input_dict = input_data.model_dump(mode="json")
        input_hash = cls._compute_input_hash(input_dict)

        user_prompt = format_uw_prompt(input_dict)
        raw_text, latency_ms = cls._call_anthropic(UW_SYSTEM_PROMPT, user_prompt)
        parsed = cls._parse_json_response(raw_text)

        # Validate against schema
        try:
            output = UnderwriteClaimOutput(
                **parsed,
                model_version=settings.anthropic_model,
                prompt_version=UW_VERSION,
            )
        except Exception as e:
            raise AnthropicServiceError(f"Output validation failed: {e}")

        metadata = {
            "input_hash": input_hash,
            "latency_ms": latency_ms,
            "model_name": settings.anthropic_model,
            "prompt_version": UW_VERSION,
            "parse_success": True,
            "raw_output": parsed,
        }
        return output, metadata

    # ── parse_eob ──────────────────────────────────────────────────────

    @classmethod
    def parse_eob(
        cls, input_data: ParseEobInput
    ) -> Tuple[ParseEobOutput, dict]:
        """Parse EOB/ERA text into structured remittance data.

        Args:
            input_data: Raw EOB text and optional matching context

        Returns:
            Tuple of (validated output, metadata dict)

        Raises:
            AnthropicServiceError: On API or parsing failure
        """
        input_dict = input_data.model_dump(mode="json")
        input_hash = cls._compute_input_hash(input_dict)

        user_prompt = format_eob_prompt(input_dict)
        raw_text, latency_ms = cls._call_anthropic(EOB_SYSTEM_PROMPT, user_prompt)
        parsed = cls._parse_json_response(raw_text)

        try:
            output = ParseEobOutput(
                **parsed,
                model_version=settings.anthropic_model,
                prompt_version=EOB_VERSION,
            )
        except Exception as e:
            raise AnthropicServiceError(f"Output validation failed: {e}")

        metadata = {
            "input_hash": input_hash,
            "latency_ms": latency_ms,
            "model_name": settings.anthropic_model,
            "prompt_version": EOB_VERSION,
            "parse_success": True,
            "raw_output": parsed,
        }
        return output, metadata

    # ── generate_ontology_updates ──────────────────────────────────────

    @classmethod
    def generate_ontology_updates(
        cls, input_data: OntologyUpdateInput
    ) -> Tuple[OntologyUpdateOutput, dict]:
        """Generate ontology update proposals from claim/remittance context.

        Args:
            input_data: Claim, funding, and remittance context

        Returns:
            Tuple of (validated output, metadata dict)

        Raises:
            AnthropicServiceError: On API or parsing failure
        """
        input_dict = input_data.model_dump(mode="json")
        input_hash = cls._compute_input_hash(input_dict)

        user_prompt = format_onto_prompt(input_dict)
        raw_text, latency_ms = cls._call_anthropic(ONTO_SYSTEM_PROMPT, user_prompt)
        parsed = cls._parse_json_response(raw_text)

        try:
            output = OntologyUpdateOutput(
                **parsed,
                model_version=settings.anthropic_model,
                prompt_version=ONTO_VERSION,
            )
        except Exception as e:
            raise AnthropicServiceError(f"Output validation failed: {e}")

        metadata = {
            "input_hash": input_hash,
            "latency_ms": latency_ms,
            "model_name": settings.anthropic_model,
            "prompt_version": ONTO_VERSION,
            "parse_success": True,
            "raw_output": parsed,
        }
        return output, metadata
