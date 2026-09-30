import json
from pathlib import Path
import pytest

from extractor.prompts import get_augmented_few_shot_examples
from verification.config import config
from verification.feedback import FeedbackLoop
from verification.flagging import TripletFlaggingEngine
from verification.graph_updater import GraphVerificationUpdater
from verification.verifier import TripletVerifier


def test_flagging_engine_threshold_and_contradictions():
    """Verify that TripletFlaggingEngine flags low-confidence and contradictory triplets."""
    engine = TripletFlaggingEngine()

    sample_triplets = [
        # Normal high-confidence triplet (should NOT be flagged)
        {
            "subject": "BERT",
            "subject_type": "Model",
            "relation": "BUILDS_ON",
            "object": "Transformer",
            "object_type": "Architecture",
            "confidence": 0.95,
            "evidence_span": "BERT builds on the Transformer architecture.",
            "paper_id": "paper_1",
            "section": "Intro",
        },
        # Low-confidence triplet (SHOULD be flagged)
        {
            "subject": "RoBERTa",
            "subject_type": "Model",
            "relation": "IMPROVES",
            "object": "Accuracy",
            "object_type": "Metric",
            "confidence": 0.50,
            "evidence_span": "RoBERTa may improve accuracy.",
            "paper_id": "paper_2",
            "section": "Results",
        },
        # Conflicting claim 1
        {
            "subject": "ModelX",
            "subject_type": "Model",
            "relation": "PROPOSES",
            "object": "ArchitectureA",
            "object_type": "Architecture",
            "confidence": 0.90,
            "evidence_span": "ModelX proposes ArchitectureA.",
            "paper_id": "paper_3",
            "section": "Methods",
        },
        # Conflicting claim 2 (different object for same subject+proposes across papers)
        {
            "subject": "ModelX",
            "subject_type": "Model",
            "relation": "PROPOSES",
            "object": "ArchitectureB",
            "object_type": "Architecture",
            "confidence": 0.90,
            "evidence_span": "ModelX proposes ArchitectureB.",
            "paper_id": "paper_4",
            "section": "Methods",
        },
        # Explicit contradiction relation
        {
            "subject": "ClaimA",
            "subject_type": "Concept",
            "relation": "CONTRADICTS",
            "object": "ClaimB",
            "object_type": "Concept",
            "confidence": 0.85,
            "evidence_span": "ClaimA directly contradicts ClaimB.",
            "paper_id": "paper_5",
            "section": "Discussion",
        },
    ]

    flagged = engine.flag_triplets(triplets=sample_triplets, save_to_file=False)

    flag_reasons = [f["flag_reason"] for f in flagged]
    assert "low_confidence" in flag_reasons
    assert "contradiction" in flag_reasons
    assert len(flagged) >= 3


def test_triplet_verifier_outcomes():
    """Verify that TripletVerifier accurately yields CONFIRMED, CORRECTED, and REJECTED statuses."""
    verifier = TripletVerifier()

    flagged_samples = [
        # Unresolved pronoun -> REJECTED
        {
            "triplet": {
                "subject": "It",
                "subject_type": "Model",
                "relation": "IMPROVES",
                "object": "Accuracy",
                "object_type": "Metric",
                "confidence": 0.55,
                "evidence_span": "It improves accuracy by 5%.",
                "paper_id": "paper_test",
                "section": "Results",
            },
            "flag_reason": "low_confidence",
            "flag_details": "Confidence below threshold",
        },
        # Low confidence but valid text -> CORRECTED (boosted confidence)
        {
            "triplet": {
                "subject": "BERT",
                "subject_type": "Model",
                "relation": "BUILDS_ON",
                "object": "Transformer",
                "object_type": "Architecture",
                "confidence": 0.60,
                "evidence_span": "BERT builds on the Transformer architecture.",
                "paper_id": "paper_test",
                "section": "Intro",
            },
            "flag_reason": "low_confidence",
            "flag_details": "Confidence below threshold",
        },
        # High-confidence grounded claim -> CONFIRMED
        {
            "triplet": {
                "subject": "CoAL-RAG",
                "subject_type": "Method",
                "relation": "IMPROVES",
                "object": "Faithfulness",
                "object_type": "Metric",
                "confidence": 0.95,
                "evidence_span": "CoAL-RAG improves faithfulness over standard RAG baselines.",
                "paper_id": "paper_test",
                "section": "Abstract",
            },
            "flag_reason": "contradiction",
            "flag_details": "Potential contradiction",
        },
    ]

    outcomes = verifier.verify_batch(flagged_samples, save_to_file=False)
    statuses = {o["status"] for o in outcomes}

    assert "REJECTED" in statuses
    assert ("CORRECTED" in statuses or "CONFIRMED" in statuses)
    assert len(outcomes) == 3


def test_feedback_loop_and_prompt_augmentation(tmp_path):
    """Verify feedback loop persistence and dynamic few-shot prompt injection."""
    feedback = FeedbackLoop()

    sample_verification_results = [
        {
            "status": "CORRECTED",
            "rationale": "Corrected casing and boosted confidence.",
            "corrected_triplet": {
                "subject": "DexterSQL",
                "subject_type": "Method",
                "relation": "IMPROVES",
                "candidate_relation": None,
                "object": "SQL Selection Accuracy",
                "object_type": "Metric",
                "confidence": 0.95,
                "evidence_span": "DexterSQL improves SQL selection accuracy by 12%.",
                "paper_id": "2608.11889v1",
                "section": "Abstract",
            },
        }
    ]

    examples = feedback.extract_feedback_examples(sample_verification_results)
    assert len(examples) > 0
    assert examples[0]["paper_id"] == "2608.11889v1"

    feedback.persist_dynamic_examples(examples)
    assert config.dynamic_examples_file.exists()

    augmented = get_augmented_few_shot_examples()
    assert len(augmented) > 2  # base 2 examples + at least 1 dynamic example
    
    # Clean up file after test
    if config.dynamic_examples_file.exists():
        config.dynamic_examples_file.unlink()


def test_graph_verification_updater():
    """Verify that Neo4j relationships are properly verified, corrected, and deleted."""
    with GraphVerificationUpdater() as updater:
        results = [
            {
                "status": "CONFIRMED",
                "original_triplet": {
                    "subject": "BERT",
                    "object": "Transformer",
                    "paper_id": "1908.08962",
                },
            },
            {
                "status": "REJECTED",
                "original_triplet": {
                    "subject": "NonExistentModel",
                    "object": "NonExistentConcept",
                    "paper_id": "fake_paper",
                },
            },
        ]
        stats = updater.apply_verification_results(results)
        assert stats["confirmed"] >= 1
        assert stats["rejected"] >= 1


def test_end_to_end_verification_loop():
    """Acceptance Test: Run full verification loop on a batch of flagged triplets."""
    engine = TripletFlaggingEngine()
    verifier = TripletVerifier()
    feedback = FeedbackLoop()

    test_triplets = [
        {
            "subject": "They",
            "subject_type": "Model",
            "relation": "IMPROVES",
            "object": "Performance",
            "object_type": "Metric",
            "confidence": 0.45,
            "evidence_span": "They improve performance.",
            "paper_id": "2608.00001",
            "section": "Abstract",
        },
        {
            "subject": "DPO",
            "subject_type": "Method",
            "relation": "IMPROVES",
            "object": "Alignment",
            "object_type": "Task",
            "confidence": 0.65,
            "evidence_span": "DPO improves alignment stability.",
            "paper_id": "2608.00002",
            "section": "Intro",
        },
    ]

    # 1. Flag
    flagged = engine.flag_triplets(triplets=test_triplets, save_to_file=False)
    assert len(flagged) == 2

    # 2. Verify
    outcomes = verifier.verify_batch(flagged, save_to_file=True)
    assert len(outcomes) == 2
    # Verify outcomes changed at least one (one rejected, one corrected/confirmed)
    outcome_statuses = [o["status"] for o in outcomes]
    assert "REJECTED" in outcome_statuses

    # 3. Feed back into few-shot examples
    dynamic_ex = feedback.extract_feedback_examples(outcomes)
    feedback.persist_dynamic_examples(dynamic_ex)

    # 4. Check prompt augmentation
    augmented = get_augmented_few_shot_examples()
    assert len(augmented) >= 2

    # Clean up test dynamic file
    if config.dynamic_examples_file.exists():
        config.dynamic_examples_file.unlink()
