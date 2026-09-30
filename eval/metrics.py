import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("metrics")


def normalize_token_str(text: str) -> str:
    """Normalize string for robust entity and relation matching."""
    clean = re.sub(r"[^a-zA-Z0-9]+", " ", str(text).strip().lower())
    return " ".join(clean.split())


def _triplets_match(t1: Dict[str, Any], t2: Dict[str, Any], threshold: float = 0.6) -> bool:
    """Check if two triplets match based on normalized subject, relation, and object overlap."""
    s1 = set(normalize_token_str(t1.get("subject", "")).split())
    s2 = set(normalize_token_str(t2.get("subject", "")).split())
    r1 = normalize_token_str(t1.get("relation", "") or t1.get("candidate_relation", ""))
    r2 = normalize_token_str(t2.get("relation", "") or t2.get("candidate_relation", ""))
    o1 = set(normalize_token_str(t1.get("object", "")).split())
    o2 = set(normalize_token_str(t2.get("object", "")).split())

    if not s1 or not s2 or not o1 or not o2:
        return False

    subj_sim = len(s1 & s2) / max(len(s1 | s2), 1)
    obj_sim = len(o1 & o2) / max(len(o1 | o2), 1)
    rel_match = (r1 == r2) or (r1 in r2) or (r2 in r1)

    return (subj_sim >= threshold) and (obj_sim >= threshold) and rel_match


def compute_extraction_metrics(
    extracted_triplets: List[Dict[str, Any]],
    ground_truth_triplets: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Compute Precision, Recall, and F1 score for triplet extraction."""
    if not extracted_triplets and not ground_truth_triplets:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    if not extracted_triplets:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": len(ground_truth_triplets)}
    if not ground_truth_triplets:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": len(extracted_triplets), "fn": 0}

    matched_gt: Set[int] = set()
    tp = 0
    fp = 0

    for ext in extracted_triplets:
        found_match = False
        for i, gt in enumerate(ground_truth_triplets):
            if i not in matched_gt and _triplets_match(ext, gt):
                matched_gt.add(i)
                tp += 1
                found_match = True
                break
        if not found_match:
            fp += 1

    fn = len(ground_truth_triplets) - len(matched_gt)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def compute_entity_linking_accuracy(
    predictions: List[Tuple[str, str]],
    ground_truth: List[Tuple[str, str]],
) -> Dict[str, float]:
    """Compute Entity-Linking / Resolution Accuracy.
    
    Each item is a tuple: (surface_mention, canonical_id).
    """
    if not ground_truth:
        return {"accuracy": 1.0, "total": 0, "correct": 0}

    gt_map = {normalize_token_str(m): c for m, c in ground_truth}
    correct = 0
    total = len(ground_truth)

    for pred_m, pred_c in predictions:
        norm_m = normalize_token_str(pred_m)
        if norm_m in gt_map and gt_map[norm_m] == pred_c:
            correct += 1

    accuracy = correct / total if total > 0 else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "total": total,
        "correct": correct,
    }


def compute_answer_faithfulness(
    answer: str,
    retrieved_context: str,
    expected_keywords: Optional[List[str]] = None,
) -> float:
    """Compute lexical and factual faithfulness score of answer grounded in retrieved context."""
    if not answer.strip():
        return 0.0

    ans_words = set(re.findall(r"\b[A-Za-z0-9\-\_]{3,}\b", answer.lower()))
    ctx_words = set(re.findall(r"\b[A-Za-z0-9\-\_]{3,}\b", retrieved_context.lower()))

    # Ignore generic common stop words
    stop_words = {
        "the", "and", "that", "this", "with", "from", "for", "are", "were", "been",
        "based", "corpus", "evidence", "across", "papers", "paper", "about", "what",
        "which", "when", "where", "into", "over", "have", "more", "such",
    }
    content_words = ans_words - stop_words

    if not content_words:
        return 1.0

    grounded_words = content_words & ctx_words
    grounding_ratio = len(grounded_words) / len(content_words)

    keyword_bonus = 0.0
    if expected_keywords:
        norm_kw = [k.lower().strip() for k in expected_keywords if k.strip()]
        matched_kw = sum(1 for k in norm_kw if k in answer.lower())
        keyword_bonus = (matched_kw / len(norm_kw)) * 0.2 if norm_kw else 0.0

    score = min(1.0, grounding_ratio * 0.8 + keyword_bonus + 0.1)
    return round(score, 4)


def compute_citation_correctness(
    predicted_citations: List[str],
    expected_citations: List[str],
) -> Dict[str, float]:
    """Compute Precision, Recall, and F1 for cited paper IDs."""
    pred_set = set(str(c).strip() for c in predicted_citations if str(c).strip())
    exp_set = set(str(c).strip() for c in expected_citations if str(c).strip())

    if not exp_set and not pred_set:
        return {"citation_precision": 1.0, "citation_recall": 1.0, "citation_f1": 1.0}
    if not pred_set:
        return {"citation_precision": 0.0, "citation_recall": 0.0, "citation_f1": 0.0}
    if not exp_set:
        return {"citation_precision": 1.0, "citation_recall": 1.0, "citation_f1": 1.0}

    intersection = pred_set & exp_set
    precision = len(intersection) / len(pred_set) if pred_set else 0.0
    recall = len(intersection) / len(exp_set) if exp_set else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "citation_precision": round(precision, 4),
        "citation_recall": round(recall, 4),
        "citation_f1": round(f1, 4),
    }


def compute_latency_metrics(latencies: List[float]) -> Dict[str, float]:
    """Compute average, median (p50), and 95th percentile (p95) latencies in seconds."""
    if not latencies:
        return {"mean_latency_sec": 0.0, "p50_latency_sec": 0.0, "p95_latency_sec": 0.0}

    sorted_l = sorted(latencies)
    mean_val = sum(sorted_l) / len(sorted_l)
    p50_idx = int(0.50 * len(sorted_l))
    p95_idx = min(int(0.95 * len(sorted_l)), len(sorted_l) - 1)

    return {
        "mean_latency_sec": round(mean_val, 4),
        "p50_latency_sec": round(sorted_l[p50_idx], 4),
        "p95_latency_sec": round(sorted_l[p95_idx], 4),
    }
