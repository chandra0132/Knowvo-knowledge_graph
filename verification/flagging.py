import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from verification.config import VerificationConfig, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("flagging")


class TripletFlaggingEngine:
    """Detects low-confidence triplets and cross-paper contradictions."""

    def __init__(self, cfg: Optional[VerificationConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()

    def _normalize_str(self, val: str) -> str:
        """Normalize entity or relation string for grouping."""
        clean = re.sub(r"[^a-zA-Z0-9]+", " ", str(val).strip().lower())
        return " ".join(clean.split())

    def flag_triplets(
        self,
        triplets: Optional[List[Dict[str, Any]]] = None,
        save_to_file: bool = True,
    ) -> List[Dict[str, Any]]:
        """Identify low-confidence triplets and contradictions from a list or file."""
        input_triplets: List[Dict[str, Any]] = []

        if triplets is not None:
            input_triplets = triplets
        elif self.cfg.all_triplets_file.exists():
            with open(self.cfg.all_triplets_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        input_triplets.append(json.loads(line))
        else:
            logger.warning(f"No triplets provided and {self.cfg.all_triplets_file} not found.")
            return []

        flagged: List[Dict[str, Any]] = []

        # 1. Low Confidence Flagging
        for t in input_triplets:
            conf = float(t.get("confidence", 1.0))
            if conf < self.cfg.confidence_threshold:
                flagged.append({
                    "triplet": t,
                    "flag_reason": "low_confidence",
                    "flag_details": f"Confidence {conf:.2f} is below threshold {self.cfg.confidence_threshold:.2f}",
                })

        # 2. Contradiction Flagging
        # Group by (normalized_subject, normalized_relation)
        groups = defaultdict(list)
        for t in input_triplets:
            subj_norm = self._normalize_str(t.get("subject", ""))
            rel_norm = self._normalize_str(t.get("relation", "") or t.get("candidate_relation", ""))
            if subj_norm and rel_norm:
                groups[(subj_norm, rel_norm)].append(t)

        for (subj_norm, rel_norm), group in groups.items():
            # If relation explicitly indicates contradiction
            if "contradict" in rel_norm:
                for t in group:
                    flagged.append({
                        "triplet": t,
                        "flag_reason": "contradiction",
                        "flag_details": f"Explicit contradiction relation: {t.get('relation')}",
                    })
                continue

            # If same subject + relation has conflicting objects across papers
            if len(group) > 1:
                objects_by_paper = defaultdict(set)
                for t in group:
                    obj_norm = self._normalize_str(t.get("object", ""))
                    paper_id = t.get("paper_id", "unknown")
                    objects_by_paper[paper_id].add(obj_norm)

                all_unique_objects = set(
                    self._normalize_str(t.get("object", "")) for t in group if t.get("object")
                )

                # If there are multiple distinct objects claimed for the same subject + relation
                if len(all_unique_objects) > 1 and rel_norm in ["proposes", "extends", "builds on", "contradicts"]:
                    for t in group:
                        flagged.append({
                            "triplet": t,
                            "flag_reason": "contradiction",
                            "flag_details": (
                                f"Subject '{t.get('subject')}' has multiple conflicting '{t.get('relation')}' "
                                f"claims across corpus: {sorted(list(all_unique_objects))}"
                            ),
                        })

        # Deduplicate flagged items by (subject, relation, object, paper_id, flag_reason)
        seen = set()
        deduped_flagged: List[Dict[str, Any]] = []
        for item in flagged:
            t = item["triplet"]
            key = (
                self._normalize_str(t.get("subject", "")),
                self._normalize_str(t.get("relation", "")),
                self._normalize_str(t.get("object", "")),
                t.get("paper_id", ""),
                item["flag_reason"],
            )
            if key not in seen:
                seen.add(key)
                deduped_flagged.append(item)

        logger.info(f"Flagged {len(deduped_flagged)} triplets (low-confidence / contradictions).")

        if save_to_file and deduped_flagged:
            with open(self.cfg.flagged_triplets_file, "w", encoding="utf-8") as f:
                for item in deduped_flagged:
                    f.write(json.dumps(item) + "\n")
            logger.info(f"Saved flagged triplets to {self.cfg.flagged_triplets_file}")

        return deduped_flagged


def main():
    engine = TripletFlaggingEngine()
    results = engine.flag_triplets()
    print(f"Total flagged triplets: {len(results)}")
    for r in results[:5]:
        print(f"  [{r['flag_reason']}] {r['triplet'].get('subject')} -{r['triplet'].get('relation')}-> {r['triplet'].get('object')} : {r['flag_details']}")


if __name__ == "__main__":
    main()
