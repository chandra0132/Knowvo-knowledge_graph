import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from extractor.config import ExtractorConfig, config
from extractor.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    FEW_SHOT_EXAMPLES,
    get_augmented_few_shot_examples,
)
from extractor.schema import CoreRelation, ExtractionResponse, ExtractedTriplet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("llm_extractor")


class KnowledgeExtractor:
    """Extracts structured triplets (subject, relation, object, confidence, evidence) from text chunks."""

    def __init__(self, cfg: Optional[ExtractorConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()
        self.langfuse_client = self._init_langfuse()
        self.genai_client = self._init_genai_client()

    def _init_langfuse(self):
        """Initialize Langfuse tracer if credentials exist in config."""
        if self.cfg.langfuse_public_key and self.cfg.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                client = Langfuse(
                    public_key=self.cfg.langfuse_public_key,
                    secret_key=self.cfg.langfuse_secret_key,
                    host=self.cfg.langfuse_host,
                )
                logger.info("Langfuse tracing initialized successfully.")
                return client
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
        else:
            logger.info("Langfuse keys not configured; tracing is disabled.")
        return None

    def _init_genai_client(self):
        """Initialize Google GenAI client if valid API key is present."""
        if (
            self.cfg.llm_api_key
            and self.cfg.llm_api_key != "your_llm_api_key_here"
        ):
            try:
                from google import genai

                client = genai.Client(api_key=self.cfg.llm_api_key)
                logger.info(f"Google GenAI client initialized with model '{self.cfg.llm_model}'.")
                return client
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")
        else:
            logger.info("No valid LLM API key configured. Using rule-assisted extraction fallback.")
        return None

    def _log_candidate_relation(self, triplet: ExtractedTriplet) -> None:
        """Log custom candidate relations to candidate_relations.jsonl for human review."""
        if not triplet.candidate_relation:
            return

        record = {
            "paper_id": triplet.paper_id,
            "section": triplet.section,
            "subject": triplet.subject,
            "subject_type": triplet.subject_type,
            "relation": (
                triplet.relation.value
                if isinstance(triplet.relation, CoreRelation)
                else str(triplet.relation)
            ),
            "candidate_relation": triplet.candidate_relation.upper().strip(),
            "object": triplet.object,
            "object_type": triplet.object_type,
            "evidence_span": triplet.evidence_span,
            "confidence": triplet.confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with open(self.cfg.candidate_relations_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _rule_based_fallback_extract(self, chunk: Dict) -> List[ExtractedTriplet]:
        """High-precision fallback extractor for scientific text when LLM key is unconfigured."""
        text = chunk["text"]
        paper_id = chunk["paper_id"]
        section = chunk["section"]
        chunk_id = chunk.get("chunk_id")

        triplets: List[ExtractedTriplet] = []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]

        patterns = [
            # PROPOSES / INTRODUCES
            (
                re.compile(
                    r"(?:We|This paper|Our work|The authors?)\s+(?:propose|proposes|introduce|introduces|present|presents|develop|develops)\s+([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:to|for|which|that|\,|\.|\s)\s*([A-Za-z0-9\-\s]{3,40}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.PROPOSES,
                "Method",
                "Task",
                None,
            ),
            # IMPROVES
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:improves|enhances|boosts|outperforms|achieves better)\s+([A-Z][A-Za-z0-9\-\s]{2,40}?)(?:\s+on|\s+over|\s+by|\.|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.IMPROVES,
                "Method",
                "Metric",
                None,
            ),
            # BUILDS_ON / EXTENDS
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:builds on|extends|is based on|leverages)\s+([A-Z][A-Za-z0-9\-\s]{2,40}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.BUILDS_ON,
                "Model",
                "Architecture",
                None,
            ),
            # EVALUATES
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:evaluates|is evaluated on|benchmarked on|tested on)\s+([A-Z][A-Za-z0-9\-\s]{2,40}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.EVALUATES,
                "Method",
                "Dataset",
                None,
            ),
            # USES
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:uses|utilizes|employs|adopts)\s+([A-Z][A-Za-z0-9\-\s]{2,40}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.USES,
                "Method",
                "Model",
                None,
            ),
            # COMPARED_WITH
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:is compared with|compared to|benchmarked against)\s+([A-Z][A-Za-z0-9\-\s]{2,40}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.COMPARED_WITH,
                "Method",
                "Method",
                None,
            ),
            # MITIGATES (Candidate relation)
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:mitigates|mitigate|reduces|reduce|prevents|prevent|alleviates|curbs)\s+([A-Za-z0-9\-\s]{3,50}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.OTHER,
                "Method",
                "Problem",
                "MITIGATES",
            ),
            # DETECTS (Candidate relation)
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:detects|detect|identifies|identify|spots)\s+([A-Za-z0-9\-\s]{3,50}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.OTHER,
                "Method",
                "Problem",
                "DETECTION_OF",
            ),
            # FINE_TUNED_ON (Candidate relation)
            (
                re.compile(
                    r"([A-Z][A-Za-z0-9\-\s]{2,30}?)\s+(?:is fine-tuned on|fine-tuned on|trained on)\s+([A-Z][A-Za-z0-9\-\s]{2,40}?)(?=\.|\,|$)",
                    re.IGNORECASE,
                ),
                CoreRelation.OTHER,
                "Model",
                "Dataset",
                "FINE_TUNED_ON",
            ),
        ]

        for sentence in sentences:
            for regex, rel, s_type, o_type, cand_rel in patterns:
                m = regex.search(sentence)
                if m:
                    subj = m.group(1).strip()
                    obj = m.group(2).strip()
                    
                    # Sanity clean
                    subj = re.sub(r"^(a|an|the)\s+", "", subj, flags=re.I).title()
                    obj = re.sub(r"^(a|an|the)\s+", "", obj, flags=re.I).title()

                    if len(subj) >= 2 and len(obj) >= 3 and subj.lower() != obj.lower():
                        t = ExtractedTriplet(
                            subject=subj[:50],
                            subject_type=s_type,
                            relation=rel,
                            candidate_relation=cand_rel,
                            object=obj[:60],
                            object_type=o_type,
                            confidence=0.88 if cand_rel is None else 0.85,
                            evidence_span=sentence,
                            paper_id=paper_id,
                            section=section,
                            chunk_id=chunk_id,
                        )
                        triplets.append(t)

        return triplets

    def extract_chunk(self, chunk: Dict) -> List[ExtractedTriplet]:
        """Extract triplets from a single text chunk via GenAI structured output or fallback."""
        text = chunk["text"]
        paper_id = chunk["paper_id"]
        section = chunk["section"]
        chunk_id = chunk.get("chunk_id")

        trace = None
        if self.langfuse_client:
            try:
                trace = self.langfuse_client.trace(
                    name="chunk_triplet_extraction",
                    metadata={"paper_id": paper_id, "section": section, "chunk_id": chunk_id},
                )
            except Exception as e:
                logger.debug(f"Langfuse trace creation error: {e}")

        triplets: List[ExtractedTriplet] = []

        if self.genai_client:
            try:
                from google.genai import types

                examples = get_augmented_few_shot_examples()
                few_shot_str = json.dumps(examples, indent=2) if examples else ""

                prompt = (
                    f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
                    f"### Reference Few-Shot Examples:\n{few_shot_str}\n\n"
                    f"Paper ID: {paper_id}\nSection: {section}\n\n"
                    f"Text Chunk:\n{text}\n\n"
                    "Return extraction JSON conforming strictly to ExtractionResponse schema."
                )

                response = self.genai_client.models.generate_content(
                    model=self.cfg.llm_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ExtractionResponse,
                        temperature=0.1,
                    ),
                )

                if response.text:
                    parsed = ExtractionResponse.model_validate_json(response.text)
                    for t in parsed.triplets:
                        # Enforce paper_id and section from chunk
                        t.paper_id = paper_id
                        t.section = section
                        t.chunk_id = chunk_id
                        triplets.append(t)

                if trace:
                    trace.update(output={"triplets_count": len(triplets)})
            except Exception as e:
                logger.warning(f"GenAI call failed on chunk {chunk_id}: {e}. Falling back.")
                triplets = self._rule_based_fallback_extract(chunk)
        else:
            triplets = self._rule_based_fallback_extract(chunk)

        # Log candidate relations and ensure all triplets carry paper_id and evidence_span
        for t in triplets:
            if t.candidate_relation:
                self._log_candidate_relation(t)

        return triplets

    def extract_paper(self, processed_json_path: Path) -> Dict:
        """Extract triplets across all chunks of a processed paper."""
        with open(processed_json_path, "r", encoding="utf-8") as f:
            paper_data = json.load(f)

        paper_id = paper_data["paper_id"]
        chunks = paper_data.get("chunks", [])

        logger.info(f"Extracting triplets for paper '{paper_id}' ({len(chunks)} chunks)...")
        all_paper_triplets: List[ExtractedTriplet] = []

        for chunk in chunks:
            triplets = self.extract_chunk(chunk)
            all_paper_triplets.extend(triplets)

        # Save paper extractions
        output_file = self.cfg.extractions_dir / f"{paper_id}.json"
        dumpable = [t.model_dump() for t in all_paper_triplets]
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "paper_id": paper_id,
                    "total_triplets": len(all_paper_triplets),
                    "triplets": dumpable,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Append to global all_triplets.jsonl
        with open(self.cfg.all_triplets_file, "a", encoding="utf-8") as f:
            for t in dumpable:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

        logger.info(
            f"Extracted {len(all_paper_triplets)} triplets for paper '{paper_id}' -> {output_file.name}"
        )
        return {"paper_id": paper_id, "triplets_count": len(all_paper_triplets)}

    def extract_corpus(self, num_papers: int = 20) -> List[Dict]:
        """Run extraction pipeline on num_papers processed JSON files."""
        json_files = sorted(list(self.cfg.processed_dir.glob("*.json")))
        target_files = json_files[:num_papers]

        logger.info(f"Starting Knowledge Extractor on {len(target_files)} papers...")
        results = []

        # Clear/reset global all_triplets.jsonl for clean run if desired
        if self.cfg.all_triplets_file.exists():
            self.cfg.all_triplets_file.unlink()

        for jf in target_files:
            try:
                res = self.extract_paper(jf)
                results.append(res)
            except Exception as e:
                logger.error(f"Failed extraction on {jf.name}: {e}")

        total_triplets = sum(r["triplets_count"] for r in results)
        logger.info(
            f"Corpus extraction complete! Extracted {total_triplets} triplets across {len(results)} papers."
        )
        return results


def main():
    extractor = KnowledgeExtractor()
    results = extractor.extract_corpus(num_papers=20)
    print(f"\nKnowledge Extraction complete across {len(results)} papers!")


if __name__ == "__main__":
    main()
