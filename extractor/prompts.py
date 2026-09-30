"""Prompts and worked few-shot examples for structured knowledge extraction."""

EXTRACTION_SYSTEM_PROMPT = """You are an expert scientific knowledge graph extractor specializing in Artificial Intelligence, Large Language Models, and NLP research.

Your task is to analyze scientific text chunks from research papers and extract precise semantic triplets (subject, relation, object) supported by explicit text evidence.

### Entity Types:
- Method (e.g., CoAL-RAG, Direct Preference Optimization, DPO)
- Model (e.g., BERT, GPT-4, LLaMA, RoBERTa)
- Architecture (e.g., Transformer, Encoder-Decoder, Attention)
- Dataset (e.g., LegalQA, CronQuestions, GSM8K, HotpotQA)
- Metric (e.g., Accuracy, ROUGE-L, Faithfulness, Hallucination Rate, BLEU)
- Problem (e.g., LLM Hallucination, Overconfidence, Memory Overhead)
- Task (e.g., Question Answering, Factuality Checking, Legal Retrieval)
- Concept (e.g., Semantic Entropy, Phase-wise Alignment)
- Author (e.g., Devlin et al., Vaswani)

### Core Fixed Relation Vocabulary:
1. PROPOSES: Subject introduces or presents Object (e.g., Paper/Model PROPOSES Method)
2. USES: Subject utilizes Object as a tool, technique, or baseline (e.g., Method USES Dataset)
3. BUILDS_ON: Subject extends or grounds itself upon Object (e.g., Model BUILDS_ON Architecture)
4. IMPROVES: Subject increases performance or reduces error on Object (e.g., Method IMPROVES Faithfulness)
5. CONTRADICTS: Subject makes a claim that directly conflicts with Object claim
6. EVALUATES: Subject benchmarks or tests performance on Object (e.g., Study EVALUATES Model)
7. AUTHORED_BY: Subject paper/method is created by Object author
8. CITES: Subject references Object paper or method
9. EXTENDS: Subject expands the scope or capabilities of Object
10. COMPARED_WITH: Subject is benchmarked directly against Object baseline

### Candidate Relations:
If NONE of the 10 fixed core relations accurately fit the relationship, set relation to "OTHER" and populate `candidate_relation` with an uppercase verb/phrase (e.g., "MITIGATES", "PREVENTS", "FINE_TUNED_ON").

### Rules:
1. Every triplet MUST include a non-empty `evidence_span` copying the exact supporting phrase or sentence from the input text.
2. Self-report a `confidence` score between 0.0 and 1.0 (1.0 = explicit factual statement, <0.7 = implicit or speculative inference).
3. Do NOT extract vague or trivial pronouns (e.g., "it", "they", "this paper").
4. Extract only facts directly stated in the text chunk. Do not hallucinate external facts.
"""

FEW_SHOT_EXAMPLES = [
    {
        "chunk_text": (
            "BERT (Devlin et al., 2019) builds on the Transformer architecture to propose deep bidirectional "
            "representations for language understanding. BERT achieves state-of-the-art accuracy on SQuAD."
        ),
        "paper_id": "1908.08962",
        "section": "1. Introduction",
        "expected_triplets": [
            {
                "subject": "BERT",
                "subject_type": "Model",
                "relation": "BUILDS_ON",
                "candidate_relation": None,
                "object": "Transformer",
                "object_type": "Architecture",
                "confidence": 0.95,
                "evidence_span": "BERT (Devlin et al., 2019) builds on the Transformer architecture",
                "paper_id": "1908.08962",
                "section": "1. Introduction",
            },
            {
                "subject": "BERT",
                "subject_type": "Model",
                "relation": "PROPOSES",
                "candidate_relation": None,
                "object": "Deep Bidirectional Representations",
                "object_type": "Concept",
                "confidence": 0.92,
                "evidence_span": "propose deep bidirectional representations for language understanding",
                "paper_id": "1908.08962",
                "section": "1. Introduction",
            },
            {
                "subject": "BERT",
                "subject_type": "Model",
                "relation": "EVALUATES",
                "candidate_relation": None,
                "object": "SQuAD",
                "object_type": "Dataset",
                "confidence": 0.90,
                "evidence_span": "BERT achieves state-of-the-art accuracy on SQuAD",
                "paper_id": "1908.08962",
                "section": "1. Introduction",
            },
        ],
    },
    {
        "chunk_text": (
            "We introduce CoAL-RAG, a novel legal retrieval-augmented generation framework. "
            "CoAL-RAG mitigates LLM hallucination and improves answer faithfulness over standard RAG baselines."
        ),
        "paper_id": "2608.17536v1",
        "section": "Abstract",
        "expected_triplets": [
            {
                "subject": "CoAL-RAG",
                "subject_type": "Method",
                "relation": "PROPOSES",
                "candidate_relation": None,
                "object": "CoAL-RAG",
                "object_type": "Method",
                "confidence": 0.98,
                "evidence_span": "We introduce CoAL-RAG, a novel legal retrieval-augmented generation framework",
                "paper_id": "2608.17536v1",
                "section": "Abstract",
            },
            {
                "subject": "CoAL-RAG",
                "subject_type": "Method",
                "relation": "OTHER",
                "candidate_relation": "MITIGATES",
                "object": "LLM Hallucination",
                "object_type": "Problem",
                "confidence": 0.95,
                "evidence_span": "CoAL-RAG mitigates LLM hallucination",
                "paper_id": "2608.17536v1",
                "section": "Abstract",
            },
            {
                "subject": "CoAL-RAG",
                "subject_type": "Method",
                "relation": "IMPROVES",
                "candidate_relation": None,
                "object": "Answer Faithfulness",
                "object_type": "Metric",
                "confidence": 0.92,
                "evidence_span": "improves answer faithfulness over standard RAG baselines",
                "paper_id": "2608.17536v1",
                "section": "Abstract",
            },
            {
                "subject": "CoAL-RAG",
                "subject_type": "Method",
                "relation": "COMPARED_WITH",
                "candidate_relation": None,
                "object": "Standard RAG",
                "object_type": "Method",
                "confidence": 0.88,
                "evidence_span": "improves answer faithfulness over standard RAG baselines",
                "paper_id": "2608.17536v1",
                "section": "Abstract",
            },
        ],
    },
]


def get_augmented_few_shot_examples(max_dynamic: int = 2):
    """Load base hardcoded few-shot examples augmented with dynamically corrected verification feedback."""
    import json
    from pathlib import Path

    dynamic_file = Path(__file__).resolve().parent.parent / "data" / "dynamic_few_shot_examples.json"
    examples = list(FEW_SHOT_EXAMPLES)

    if dynamic_file.exists():
        try:
            with open(dynamic_file, "r", encoding="utf-8") as f:
                dynamic_list = json.load(f)
                if isinstance(dynamic_list, list) and dynamic_list:
                    examples.extend(dynamic_list[:max_dynamic])
        except Exception:
            pass

    return examples

