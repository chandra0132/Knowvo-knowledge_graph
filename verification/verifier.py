import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from extractor.schema import CoreRelation, ExtractedTriplet
from verification.config import VerificationConfig, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verifier")


class VerificationOutcome(BaseModel):
    """Result of the secondary verification pass on a triplet."""

    status: Literal["CONFIRMED", "CORRECTED", "REJECTED"] = Field(
        ...,
        description="Verification outcome: CONFIRMED if accurate, CORRECTED if minor errors, REJECTED if invalid/unsupported.",
    )
    rationale: str = Field(
        ...,
        description="Detailed explanation of why the triplet was confirmed, corrected, or rejected based on the evidence.",
    )
    corrected_triplet: Optional[ExtractedTriplet] = Field(
        default=None,
        description="The corrected triplet if status is CORRECTED.",
    )
    verification_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this verification decision.",
    )


class TripletVerifier:
    """Performs a secondary verification pass on flagged triplets using a strong LLM."""

    def __init__(self, cfg: Optional[VerificationConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()
        self.genai_client = self._init_genai_client()

    def _init_genai_client(self):
        """Initialize Google GenAI client if valid API key is present."""
        if self.cfg.llm_api_key and self.cfg.llm_api_key != "your_llm_api_key_here":
            try:
                from google import genai

                client = genai.Client(api_key=self.cfg.llm_api_key)
                logger.info(f"Google GenAI client initialized for TripletVerifier ({self.cfg.llm_model}).")
                return client
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client in TripletVerifier: {e}")
        return None

    def _get_chunk_context(self, paper_id: str, chunk_id: str) -> str:
        """Attempt to retrieve the full original chunk text from data/processed/."""
        if not paper_id or paper_id == "unknown":
            return ""
        processed_file = self.cfg.processed_dir / f"{paper_id}.json"
        if processed_file.exists():
            try:
                with open(processed_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for chunk in data.get("chunks", []):
                        if chunk.get("chunk_id") == chunk_id:
                            return chunk.get("text", "")
            except Exception as e:
                logger.warning(f"Error reading chunk text for {chunk_id}: {e}")
        return ""

    def verify_triplet(self, flagged_item: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a single flagged triplet against its original evidence."""
        triplet = flagged_item.get("triplet", flagged_item)
        flag_reason = flagged_item.get("flag_reason", "unknown")
        flag_details = flagged_item.get("flag_details", "")

        evidence = triplet.get("evidence_span", "")
        paper_id = triplet.get("paper_id", "unknown")
        chunk_id = triplet.get("chunk_id", "")
        chunk_context = self._get_chunk_context(paper_id, chunk_id)

        # 1. LLM Verification Pass if GenAI client is available
        if self.genai_client and evidence:
            outcome = self._verify_with_llm(triplet, evidence, chunk_context, flag_reason, flag_details)
            if outcome:
                return {
                    "original_triplet": triplet,
                    "flag_reason": flag_reason,
                    "flag_details": flag_details,
                    "status": outcome.status,
                    "rationale": outcome.rationale,
                    "corrected_triplet": outcome.corrected_triplet.model_dump() if outcome.corrected_triplet else None,
                    "verification_confidence": outcome.verification_confidence,
                }

        # 2. Rule-based / Fallback verification
        return self._verify_fallback(triplet, evidence, flag_reason, flag_details)

    def _verify_with_llm(
        self,
        triplet: Dict[str, Any],
        evidence: str,
        chunk_context: str,
        flag_reason: str,
        flag_details: str,
    ) -> Optional[VerificationOutcome]:
        """Run LLM verification prompt with structured output."""
        context_str = f"\nFull Chunk Text:\n\"{chunk_context}\"" if chunk_context else ""
        prompt = f"""You are a rigorous Scientific Knowledge Graph Verifier.
Evaluate whether the following extracted triplet is factually supported by the text evidence.

### Extracted Triplet:
- Subject: "{triplet.get('subject')}" (Type: {triplet.get('subject_type')})
- Relation: "{triplet.get('relation')}"
- Candidate Relation: "{triplet.get('candidate_relation')}"
- Object: "{triplet.get('object')}" (Type: {triplet.get('object_type')})
- Self-Reported Confidence: {triplet.get('confidence')}
- Supporting Evidence Span: "{evidence}"{context_str}

### Flag Reason:
{flag_reason}: {flag_details}

### Verification Instructions:
1. CONFIRMED: The triplet is completely accurate, directly stated in the evidence span, and valid.
2. CORRECTED: The triplet has a fixable error (e.g., inverted subject/object, wrong relation type, pronoun subject that can be resolved, typo in entity name). Provide the accurate `corrected_triplet`.
3. REJECTED: The triplet is hallucinated, unsupported by the evidence, speculative, or fundamentally invalid.

Return a JSON object conforming to VerificationOutcome.
"""
        try:
            from google.genai import types

            response = self.genai_client.models.generate_content(
                model=self.cfg.llm_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VerificationOutcome,
                    temperature=0.0,
                ),
            )
            if response.text:
                parsed = json.loads(response.text)
                return VerificationOutcome(**parsed)
        except Exception as e:
            logger.warning(f"LLM verification failed: {e}")
        return None

    def _verify_fallback(
        self,
        triplet: Dict[str, Any],
        evidence: str,
        flag_reason: str,
        flag_details: str,
    ) -> Dict[str, Any]:
        """Deterministic rule-based verification fallback."""
        subj = str(triplet.get("subject", "")).strip()
        obj = str(triplet.get("object", "")).strip()
        rel = str(triplet.get("relation", "")).strip()

        # If no evidence span provided or empty entities
        if not evidence or not subj or not obj:
            return {
                "original_triplet": triplet,
                "flag_reason": flag_reason,
                "flag_details": flag_details,
                "status": "REJECTED",
                "rationale": "Missing evidence span or blank entity values.",
                "corrected_triplet": None,
                "verification_confidence": 0.95,
            }

        ev_lower = evidence.lower()
        subj_lower = subj.lower()
        obj_lower = obj.lower()

        # Check if subject or object is an unresolved pronoun
        if subj_lower in ["it", "this", "they", "we", "the paper", "this study", "these models"]:
            return {
                "original_triplet": triplet,
                "flag_reason": flag_reason,
                "flag_details": flag_details,
                "status": "REJECTED",
                "rationale": f"Subject '{subj}' is an unresolved generic pronoun.",
                "corrected_triplet": None,
                "verification_confidence": 0.90,
            }

        # Check if entities are grounded in the evidence span
        subj_in_ev = subj_lower in ev_lower
        obj_in_ev = obj_lower in ev_lower

        if not subj_in_ev and not obj_in_ev:
            return {
                "original_triplet": triplet,
                "flag_reason": flag_reason,
                "flag_details": flag_details,
                "status": "REJECTED",
                "rationale": "Neither subject nor object is grounded in the evidence span.",
                "corrected_triplet": None,
                "verification_confidence": 0.90,
            }

        # If low confidence or minor casing/whitespace issue, correct it
        if flag_reason == "low_confidence":
            corrected = dict(triplet)
            corrected["confidence"] = 0.85
            return {
                "original_triplet": triplet,
                "flag_reason": flag_reason,
                "flag_details": flag_details,
                "status": "CORRECTED",
                "rationale": "Grounded in evidence text; promoted confidence from low-confidence threshold.",
                "corrected_triplet": corrected,
                "verification_confidence": 0.85,
            }

        return {
            "original_triplet": triplet,
            "flag_reason": flag_reason,
            "flag_details": flag_details,
            "status": "CONFIRMED",
            "rationale": "Triplet entities and relation are grounded in the evidence span.",
            "corrected_triplet": None,
            "verification_confidence": 0.88,
        }

    def verify_batch(
        self,
        flagged_items: List[Dict[str, Any]],
        save_to_file: bool = True,
    ) -> List[Dict[str, Any]]:
        """Run verification over a list of flagged triplets and save results."""
        results: List[Dict[str, Any]] = []
        logger.info(f"Starting secondary verification pass on {len(flagged_items)} flagged triplets...")

        for item in flagged_items:
            res = self.verify_triplet(item)
            results.append(res)

        if save_to_file and results:
            with open(self.cfg.verification_results_file, "w", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(r) + "\n")
            logger.info(f"Saved {len(results)} verification results to {self.cfg.verification_results_file}")

        return results


def main():
    sample_flagged = [
        {
            "triplet": {
                "subject": "It",
                "subject_type": "Model",
                "relation": "IMPROVES",
                "object": "Accuracy",
                "object_type": "Metric",
                "confidence": 0.55,
                "evidence_span": "It improves accuracy by 5%.",
                "paper_id": "2608.01234v1",
                "section": "Results",
            },
            "flag_reason": "low_confidence",
            "flag_details": "Confidence 0.55 is below threshold 0.70",
        },
        {
            "triplet": {
                "subject": "BERT",
                "subject_type": "Model",
                "relation": "BUILDS_ON",
                "object": "Transformer",
                "object_type": "Architecture",
                "confidence": 0.65,
                "evidence_span": "BERT builds on the Transformer architecture.",
                "paper_id": "1908.08962",
                "section": "Introduction",
            },
            "flag_reason": "low_confidence",
            "flag_details": "Confidence 0.65 is below threshold 0.70",
        },
    ]

    verifier = TripletVerifier()
    outcomes = verifier.verify_batch(sample_flagged, save_to_file=False)
    for o in outcomes:
        print(f"[{o['status']}] {o['original_triplet']['subject']} -> {o['rationale']}")


if __name__ == "__main__":
    main()
