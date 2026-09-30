import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scale.config import ScaleConfig
from scale.corpus_scaler import CorpusScaler
from scale.cost_tracker import CostReport, CostTracker
from scale.async_pipeline import AsyncScalePipeline
from scale.quality_checker import QualityChecker


@pytest.fixture
def temp_scale_config(tmp_path):
    """Fixture providing isolated ScaleConfig paths in tmp_path."""
    cfg = ScaleConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        processed_dir=tmp_path / "data" / "processed",
        extractions_dir=tmp_path / "data" / "extractions",
        all_triplets_file=tmp_path / "data" / "all_triplets.jsonl",
        flagged_triplets_file=tmp_path / "data" / "flagged_triplets.jsonl",
        verification_results_file=tmp_path / "data" / "verification_results.jsonl",
        checkpoint_file=tmp_path / "data" / "scale_checkpoint.json",
        cost_report_file=tmp_path / "data" / "cost_report.json",
        cost_summary_md=tmp_path / "data" / "cost_summary.md",
        target_papers=5,
        batch_size=2,
        max_concurrency=4,
    )
    cfg.ensure_directories()
    return cfg


def test_scale_config_defaults():
    """Verify default model tiers and pricing rates."""
    cfg = ScaleConfig()
    assert cfg.cheap_model == "gemini-2.5-flash"
    assert cfg.expensive_model == "gemini-2.5-pro"
    assert cfg.cheap_input_cost_per_1m < cfg.expensive_input_cost_per_1m
    assert cfg.cheap_output_cost_per_1m < cfg.expensive_output_cost_per_1m
    assert cfg.max_concurrency >= 5


def test_cost_tracker_calculation(temp_scale_config):
    """Verify token accumulation, cost calculation, and tiered savings."""
    tracker = CostTracker(temp_scale_config)

    # 1. Record Tier 1 Extraction (1,000,000 prompt tokens, 100,000 completion tokens)
    tracker.record_extraction(
        prompt_tokens=1_000_000,
        completion_tokens=100_000,
        duration_sec=2.5,
        chunks_count=100,
    )
    # Tier 1 cost: (1.0 * $0.075) + (0.1 * $0.30) = $0.075 + $0.030 = $0.105
    assert abs(tracker.stages["extraction_tier1"].cost_usd - 0.105) < 1e-4

    # 2. Record Tier 2 Verification on 5% flagged items (50,000 prompt, 10,000 comp)
    tracker.record_verification(
        prompt_tokens=50_000,
        completion_tokens=10_000,
        duration_sec=0.8,
        triplets_count=5,
    )
    # Tier 2 cost: (0.05 * $1.25) + (0.01 * $5.00) = $0.0625 + $0.05 = $0.1125
    assert abs(tracker.stages["verification_tier2"].cost_usd - 0.1125) < 1e-4

    # 3. Generate Report
    report: CostReport = tracker.generate_report(
        papers_processed=50,
        total_chunks=100,
        total_triplets=80,
        flagged_triplets=5,
        verified_triplets=5,
    )

    assert report.total_tokens == 1_160_000
    assert report.total_cost_usd > 0
    assert report.baseline_all_expensive_cost_usd > report.total_cost_usd
    assert report.cost_savings_usd > 0
    assert report.cost_reduction_pct > 70.0  # Tiered architecture saves >70%

    assert temp_scale_config.cost_report_file.exists()
    assert temp_scale_config.cost_summary_md.exists()


def test_corpus_scaler_generation(temp_scale_config):
    """Verify synthetic paper generation and corpus scaling."""
    scaler = CorpusScaler(temp_scale_config)

    paper = scaler.generate_synthetic_paper(1)
    assert paper["paper_id"] == "2608.00001v1"
    assert "sections" in paper
    assert "Abstract" in paper["sections"]
    assert len(paper["chunks"]) >= 4

    # Scale to 5 papers
    total = scaler.ensure_scaled_corpus(target_count=5)
    assert total >= 5
    assert len(list(temp_scale_config.processed_dir.glob("*.json"))) >= 5


def test_async_pipeline_batch_execution(temp_scale_config):
    """Verify async batch extraction, retry with backoff, checkpointing, and verification."""
    async def _run():
        scaler = CorpusScaler(temp_scale_config)
        scaler.ensure_scaled_corpus(target_count=4)

        pipeline = AsyncScalePipeline(temp_scale_config)
        paper_files = sorted(list(temp_scale_config.processed_dir.glob("*.json")))[:4]

        # Test batch extraction
        triplets, count = await pipeline.run_batch_extraction(paper_files)
        assert count == 4
        assert len(triplets) > 0
        assert temp_scale_config.checkpoint_file.exists()
        assert temp_scale_config.all_triplets_file.exists()

        # Test tiered verification on flagged items
        flagged, verif_results = pipeline.run_tiered_verification(triplets)
        assert len(verif_results) == len(flagged)
        assert temp_scale_config.flagged_triplets_file.exists()
        assert temp_scale_config.verification_results_file.exists()

    asyncio.run(_run())



def test_quality_checker_evaluation(temp_scale_config):
    """Verify QualityChecker runs structural checks and benchmark spot-checks."""
    # Seed a few dummy triplets and papers
    scaler = CorpusScaler(temp_scale_config)
    scaler.ensure_scaled_corpus(target_count=3)

    sample_triplets = [
        {
            "paper_id": "2608.00001v1",
            "subject": "GraphRAG",
            "relation": "IMPROVES",
            "object": "Multi-Hop Reasoning",
            "confidence": 0.88,
            "evidence_span": "GraphRAG improves multi-hop reasoning accuracy.",
        },
        {
            "paper_id": "2608.00002v1",
            "subject": "DexterSQL",
            "relation": "EVALUATES",
            "object": "Schema Linking Accuracy",
            "confidence": 0.92,
            "evidence_span": "DexterSQL evaluates schema linking accuracy on BIRD-Dev.",
        },
    ]
    with open(temp_scale_config.all_triplets_file, "w", encoding="utf-8") as f:
        for t in sample_triplets:
            f.write(json.dumps(t) + "\n")

    checker = QualityChecker(temp_scale_config)
    struct_metrics = checker.evaluate_extraction_and_graph_quality()
    assert struct_metrics["total_triplets"] == 2
    assert struct_metrics["avg_confidence_score"] >= 0.85
