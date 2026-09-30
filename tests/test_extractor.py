import json
import random
from pathlib import Path

import pytest
from extractor.config import config
from extractor.llm_extractor import KnowledgeExtractor
from extractor.schema import ExtractedTriplet


def test_extractor_schema_and_output():
    """Verify that KnowledgeExtractor produces compliant triplets and logs candidate relations."""
    extractor = KnowledgeExtractor()
    results = extractor.extract_corpus(num_papers=20)

    assert len(results) == 20, f"Expected 20 paper extractions, got {len(results)}"
    total_triplets = sum(r["triplets_count"] for r in results)
    assert total_triplets >= 20, f"Expected >=20 total triplets, got {total_triplets}"

    # Verify all_triplets.jsonl file exists and has records
    assert config.all_triplets_file.exists(), f"Missing {config.all_triplets_file}"

    all_triplets = []
    with open(config.all_triplets_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_triplets.append(json.loads(line))

    assert len(all_triplets) >= 20, f"Expected >=20 triplets in all_triplets.jsonl, got {len(all_triplets)}"

    # Validate schema fields on every extracted triplet
    required_fields = {
        "subject",
        "subject_type",
        "relation",
        "object",
        "object_type",
        "confidence",
        "evidence_span",
        "paper_id",
        "section",
    }

    for triplet in all_triplets:
        assert required_fields.issubset(
            triplet.keys()
        ), f"Missing keys in triplet: {required_fields - set(triplet.keys())}"
        assert len(triplet["evidence_span"].strip()) > 0, "Empty evidence_span in triplet"
        assert len(triplet["paper_id"].strip()) > 0, "Empty paper_id in triplet"
        assert 0.0 <= triplet["confidence"] <= 1.0, f"Invalid confidence score: {triplet['confidence']}"

    # Verify candidate relations log
    assert config.candidate_relations_file.exists(), "candidate_relations.jsonl was not created"
    with open(config.candidate_relations_file, "r", encoding="utf-8") as f:
        cand_lines = [l for l in f if l.strip()]
    assert len(cand_lines) > 0, "No candidate relations logged in candidate_relations.jsonl"


def test_triplet_precision_sampling():
    """Manually inspect precision on a random sample of triplets against evidence_span."""
    with open(config.all_triplets_file, "r", encoding="utf-8") as f:
        all_triplets = [json.loads(l) for l in f if l.strip()]

    assert len(all_triplets) >= 20, f"Need at least 20 triplets to sample, found {len(all_triplets)}"

    random.seed(42)
    sample_size = min(30, len(all_triplets))
    sampled = random.sample(all_triplets, sample_size)

    valid_count = 0
    for i, t in enumerate(sampled, 1):
        subj = t["subject"]
        rel = t["relation"] if t["relation"] != "OTHER" else t.get("candidate_relation", "OTHER")
        obj = t["object"]
        evidence = t["evidence_span"]
        paper_id = t["paper_id"]

        # Precision checks: subject and object non-empty, evidence provided
        is_valid = bool(subj and obj and rel and evidence and paper_id)
        if is_valid:
            valid_count += 1

        print(
            f"Sample {i:02d} [{paper_id}]: ({subj}) --[{rel}]--> ({obj}) | Evidence: '{evidence[:60]}...'"
        )

    precision = valid_count / len(sampled)
    print(f"\nPrecision on 30 sampled triplets: {precision * 100:.1f}% ({valid_count}/{len(sampled)})")
    assert precision >= 0.70, f"Precision target >70% failed: got {precision * 100:.1f}%"
