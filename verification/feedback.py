import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from verification.config import VerificationConfig, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("feedback")


class FeedbackLoop:
    """Collects verification corrections and feeds them back into extraction prompt examples."""

    def __init__(self, cfg: Optional[VerificationConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()

    def load_verification_results(self) -> List[Dict[str, Any]]:
        """Load verification results from file."""
        if not self.cfg.verification_results_file.exists():
            return []
        results = []
        with open(self.cfg.verification_results_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except Exception as e:
                        logger.warning(f"Error parsing verification result line: {e}")
        return results

    def extract_feedback_examples(
        self, verification_results: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Extract high-value corrected or confirmed triplets into few-shot examples."""
        results = verification_results if verification_results is not None else self.load_verification_results()
        dynamic_examples: List[Dict[str, Any]] = []

        # Group corrected triplets by chunk/paper to create coherent few-shot examples
        by_chunk: Dict[str, List[Dict[str, Any]]] = {}

        for item in results:
            status = item.get("status")
            triplet = None
            if status == "CORRECTED" and item.get("corrected_triplet"):
                triplet = item["corrected_triplet"]
            elif status == "CONFIRMED":
                triplet = item.get("original_triplet")

            if triplet and triplet.get("evidence_span"):
                paper_id = triplet.get("paper_id", "unknown")
                section = triplet.get("section", "Abstract")
                evidence = triplet.get("evidence_span", "").strip()

                chunk_key = f"{paper_id}_{section}"
                if chunk_key not in by_chunk:
                    by_chunk[chunk_key] = []
                by_chunk[chunk_key].append(triplet)

        for chunk_key, triplets in by_chunk.items():
            if not triplets:
                continue
            first_t = triplets[0]
            # Use evidence span or synthetic snippet
            chunk_text = " ".join([t.get("evidence_span", "") for t in triplets if t.get("evidence_span")])
            if not chunk_text:
                continue

            dynamic_examples.append({
                "chunk_text": chunk_text,
                "paper_id": first_t.get("paper_id", "unknown"),
                "section": first_t.get("section", "Abstract"),
                "expected_triplets": triplets,
                "source": "verification_feedback",
            })

        logger.info(f"Generated {len(dynamic_examples)} dynamic few-shot feedback examples.")
        return dynamic_examples

    def persist_dynamic_examples(self, examples: List[Dict[str, Any]]) -> Path:
        """Save dynamic examples to data/dynamic_few_shot_examples.json."""
        with open(self.cfg.dynamic_examples_file, "w", encoding="utf-8") as f:
            json.dump(examples, f, indent=2)
        logger.info(f"Persisted dynamic few-shot examples to {self.cfg.dynamic_examples_file}")
        return self.cfg.dynamic_examples_file

    def load_dynamic_examples(self) -> List[Dict[str, Any]]:
        """Load stored dynamic few-shot examples if they exist."""
        if not self.cfg.dynamic_examples_file.exists():
            return []
        try:
            with open(self.cfg.dynamic_examples_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load dynamic few-shot examples: {e}")
            return []

    def get_combined_few_shot_examples(
        self, base_examples: List[Dict[str, Any]], max_dynamic: int = 3
    ) -> List[Dict[str, Any]]:
        """Combine base hardcoded few-shot examples with dynamically generated feedback examples."""
        dynamic = self.load_dynamic_examples()
        if not dynamic:
            return base_examples
        return base_examples + dynamic[:max_dynamic]


def main():
    feedback = FeedbackLoop()
    examples = feedback.extract_feedback_examples()
    if examples:
        feedback.persist_dynamic_examples(examples)
        print(f"Saved {len(examples)} feedback examples.")
    else:
        print("No feedback examples to save.")


if __name__ == "__main__":
    main()
