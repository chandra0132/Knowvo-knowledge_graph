# Self-Improving Knowledge Graph: Evaluation Benchmark Report

**Generated At:** 2026-09-26T16:39:24.729144+00:00  
**Status:** ALL METRICS POPULATED

---

## 1. Executive Summary & Core Metrics Table

| Metric Category | Metric Name | Score / Value | Target / Benchmark |
| :--- | :--- | :--- | :--- |
| **Knowledge Extraction** | Extraction Precision | **100.0%** | >= 80.0% |
| | Extraction Recall | **23.1%** | >= 75.0% |
| | Extraction F1-Score | **37.5%** | >= 75.0% |
| **Entity Resolution** | Entity-Linking Accuracy | **100.0%** | >= 90.0% |
| **Answer Quality** | Answer Faithfulness | **36.1%** | >= 85.0% |
| **Citation Correctness** | Citation Precision | **0.0%** | >= 70.0% |
| | Citation Recall | **0.0%** | >= 65.0% |
| | Citation F1-Score | **0.0%** | >= 65.0% |
| **System Latency** | Mean Query Latency | **1.331 s** | <= 2.500 s |
| | Median Latency (p50) | **0.029 s** | <= 2.000 s |
| | 95th Percentile (p95) | **6.425 s** | <= 4.000 s |

---

## 2. Extraction & Entity Resolution Performance

- **Triplets Extracted (Sample):** 3
- **Ground Truth Triplets:** 13
- **True Positives:** 3 | **False Positives:** 0 | **False Negatives:** 10
- **Entity Mentions Evaluated:** 25 (25 correctly mapped to canonical entity IDs)

---

## 3. Detailed Question-Answering Evaluation (5 Questions)

| ID | Question Preview | Category | Faithfulness | Citation Prec. | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `qa_01` | How do recent methods mitigate LLM hallucination i... | Mitigation | 0.43 | 0.00 | 6.43s |
| `qa_02` | Which models build on or extend the Transformer ar... | Architecture | 0.41 | 0.00 | 0.03s |
| `qa_03` | What datasets or benchmarks are used to evaluate f... | Evaluation | 0.36 | 0.00 | 0.02s |
| `qa_04` | How does CoAL-RAG or DexterSQL improve baseline re... | Performance | 0.29 | 0.00 | 0.03s |
| `qa_05` | What are the main causes or categories of hallucin... | Categorization | 0.31 | 0.00 | 0.16s |

---
*Report automatically produced by `EvaluationRunner` (Phase 8).*
