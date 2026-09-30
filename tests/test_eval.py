import json
from pathlib import Path
import pytest

from eval.config import config
from eval.eval_runner import EvaluationRunner
from eval.metrics import (
    compute_answer_faithfulness,
    compute_citation_correctness,
    compute_entity_linking_accuracy,
    compute_extraction_metrics,
    compute_latency_metrics,
)


def test_metrics_calculation():
    """Verify individual evaluation metric calculations."""
    # 1. Extraction Metrics
    extracted = [
        {"subject": "BERT", "relation": "BUILDS_ON", "object": "Transformer"},
        {"subject": "GPT-4", "relation": "IMPROVES", "object": "Accuracy"},
    ]
    ground_truth = [
        {"subject": "BERT", "relation": "BUILDS_ON", "object": "Transformer"},
        {"subject": "RoBERTa", "relation": "EXTENDS", "object": "BERT"},
    ]
    ext_metrics = compute_extraction_metrics(extracted, ground_truth)
    assert ext_metrics["precision"] == 0.5
    assert ext_metrics["recall"] == 0.5
    assert ext_metrics["f1"] == 0.5

    # 2. Entity Linking Accuracy
    pred_entities = [("BERT Model", "ent_bert"), ("GPT4", "ent_gpt_4")]
    gt_entities = [("BERT Model", "ent_bert"), ("GPT4", "ent_gpt_4")]
    el_metrics = compute_entity_linking_accuracy(pred_entities, gt_entities)
    assert el_metrics["accuracy"] == 1.0

    # 3. Answer Faithfulness
    answer = "DexterSQL improves SQL selection accuracy by using structurally similar training examples."
    context = "DexterSQL improves SQL selection accuracy over baseline and uses structurally similar training examples."
    faithfulness = compute_answer_faithfulness(answer, context, ["DexterSQL", "accuracy"])
    assert faithfulness >= 0.80

    # 4. Citation Correctness
    pred_citations = ["2608.11889v1", "2608.14210v1"]
    exp_citations = ["2608.11889v1"]
    cit_metrics = compute_citation_correctness(pred_citations, exp_citations)
    assert cit_metrics["citation_precision"] == 0.5
    assert cit_metrics["citation_recall"] == 1.0

    # 5. Latency Metrics
    latencies = [0.10, 0.20, 0.30, 0.40, 0.50]
    lat_metrics = compute_latency_metrics(latencies)
    assert lat_metrics["mean_latency_sec"] == 0.30
    assert lat_metrics["p50_latency_sec"] == 0.30


def test_benchmark_dataset_integrity():
    """Verify that QA benchmark and labeled extraction datasets are present and valid."""
    assert config.qa_benchmark_file.exists(), f"Missing {config.qa_benchmark_file}"
    assert config.labeled_extraction_file.exists(), f"Missing {config.labeled_extraction_file}"

    with open(config.qa_benchmark_file, "r", encoding="utf-8") as f:
        qa_data = json.load(f)

    assert len(qa_data) >= 20, f"Expected >=20 benchmark questions, found {len(qa_data)}"
    sample_qa = qa_data[0]
    assert "id" in sample_qa
    assert "question" in sample_qa
    assert "expected_paper_citations" in sample_qa
    assert "expected_evidence_keywords" in sample_qa

    with open(config.labeled_extraction_file, "r", encoding="utf-8") as f:
        labeled_data = json.load(f)

    assert len(labeled_data) >= 5
    sample_lab = labeled_data[0]
    assert "chunk_id" in sample_lab
    assert "ground_truth_triplets" in sample_lab
    assert len(sample_lab["ground_truth_triplets"]) > 0


def test_evaluation_runner_generates_report():
    """Acceptance test: Run evaluation benchmark and verify that populated reports are generated."""
    with EvaluationRunner() as runner:
        report = runner.run_full_evaluation(max_qa_items=5)

        assert "evaluation_metrics" in report
        metrics = report["evaluation_metrics"]

        # Extraction metrics
        assert "extraction" in metrics
        assert metrics["extraction"]["precision"] >= 0.0
        assert metrics["extraction"]["recall"] >= 0.0
        assert metrics["extraction"]["f1"] >= 0.0

        # Entity Linking metrics
        assert "entity_linking" in metrics
        assert metrics["entity_linking"]["accuracy"] >= 0.0

        # Faithfulness
        assert "faithfulness" in metrics
        assert metrics["faithfulness"]["average_answer_faithfulness"] > 0.0

        # Citation correctness
        assert "citation_correctness" in metrics
        assert metrics["citation_correctness"]["precision"] >= 0.0

        # Latency
        assert "latency" in metrics
        assert metrics["latency"]["mean_latency_sec"] > 0.0

        # Ensure files are created on disk and populated
        assert config.evaluation_report_json.exists()
        assert config.evaluation_report_md.exists()

        with open(config.evaluation_report_md, "r", encoding="utf-8") as f:
            md_text = f.read()

        assert "Evaluation Benchmark Report" in md_text
        assert "Extraction Precision" in md_text
        assert "Mean Query Latency" in md_text
