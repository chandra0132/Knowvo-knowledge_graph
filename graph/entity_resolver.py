import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from graph.config import GraphConfig, config
from graph.neo4j_client import Neo4jGraphClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("entity_resolver")


class EntityResolver:
    """Disambiguates and merges duplicate entity nodes via embedding blocking and LLM/rule adjudication."""

    def __init__(self, cfg: Optional[GraphConfig] = None, sim_threshold: float = 0.70):
        self.cfg = cfg or config
        self.sim_threshold = sim_threshold
        self.canonical_map_file = self.cfg.data_dir / "canonical_entities.json"
        self._embedder = None

    @property
    def embedder(self):
        """Lazy load SentenceTransformer embedder if available."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading SentenceTransformer model 'all-MiniLM-L6-v2'...")
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except (ImportError, Exception) as e:
                logger.debug(f"SentenceTransformer not available ({e}), using string similarity fallback.")
                self._embedder = False
        return self._embedder if self._embedder is not False else None

    def load_canonical_map(self) -> Dict[str, dict]:
        """Load persisted canonical entity mapping table."""
        if not self.canonical_map_file.exists():
            return {}
        try:
            with open(self.canonical_map_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load canonical map: {e}")
            return {}

    def save_canonical_map(self, canonical_map: Dict[str, dict]) -> None:
        """Persist canonical entity table to data/canonical_entities.json."""
        with open(self.canonical_map_file, "w", encoding="utf-8") as f:
            json.dump(canonical_map, f, indent=2, ensure_ascii=False)
        logger.info(f"Persisted {len(canonical_map)} canonical entities to {self.canonical_map_file.name}")

    def normalize_name(self, name) -> str:
        """Clean and normalize string for comparison."""
        if isinstance(name, list):
            name = name[0] if name else ""
        clean = re.sub(r"[^\w\s\-]+", " ", str(name)).strip()
        clean = re.sub(r"\s+", " ", clean)
        return clean

    def block_candidate_pairs(
        self, entities: List[Dict[str, str]]
    ) -> List[Tuple[Dict[str, str], Dict[str, str], float]]:
        """Block candidate entity pairs using embedding cosine similarity and token overlaps."""
        if len(entities) < 2:
            return []

        names = [
            str(e["name"][0]) if isinstance(e.get("name"), list) else str(e.get("name", ""))
            for e in entities
        ]

        if self.embedder is not None:
            try:
                from sklearn.metrics.pairwise import cosine_similarity
                logger.info(f"Computing embeddings for {len(names)} entities...")
                embeddings = self.embedder.encode(names, show_progress_bar=False)
                sim_matrix = cosine_similarity(embeddings)
                candidate_pairs = []
                for i in range(len(entities)):
                    for j in range(i + 1, len(entities)):
                        e1, e2 = entities[i], entities[j]
                        sim = float(sim_matrix[i][j])
                        n1 = self.normalize_name(e1.get("name", "")).lower()
                        n2 = self.normalize_name(e2.get("name", "")).lower()
                        if n1 == n2 or sim >= self.sim_threshold:
                            candidate_pairs.append((e1, e2, sim))
                logger.info(f"Blocked {len(candidate_pairs)} candidate pairs for adjudication.")
                return candidate_pairs
            except Exception as e:
                logger.warning(f"Embedding blocking fallback: {e}")

        # Lightweight fallback: string ratio
        from difflib import SequenceMatcher
        candidate_pairs = []
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                e1, e2 = entities[i], entities[j]
                n1 = self.normalize_name(e1.get("name", "")).lower()
                n2 = self.normalize_name(e2.get("name", "")).lower()
                sim = SequenceMatcher(None, n1, n2).ratio()
                if n1 == n2 or sim >= self.sim_threshold:
                    candidate_pairs.append((e1, e2, sim))

        logger.info(f"Blocked {len(candidate_pairs)} candidate pairs for adjudication (string matching).")
        return candidate_pairs

    def adjudicate_pair(self, e1: Dict[str, str], e2: Dict[str, str], sim: float) -> Tuple[bool, str, str]:
        """
        Adjudicate whether e1 and e2 refer to the exact same scientific entity.
        Returns: (should_merge: bool, canonical_name: str, alias_name: str)
        """
        name1 = str(e1["name"][0]) if isinstance(e1.get("name"), list) else str(e1.get("name", ""))
        name2 = str(e2["name"][0]) if isinstance(e2.get("name"), list) else str(e2.get("name", ""))

        name1 = name1.strip()
        name2 = name2.strip()

        norm1 = self.normalize_name(name1).lower()
        norm2 = self.normalize_name(name2).lower()

        # Reject distinct numeric versions (e.g. GPT-4 vs GPT-3.5)
        num1 = re.findall(r"\b\d+(?:\.\d+)?\b", name1)
        num2 = re.findall(r"\b\d+(?:\.\d+)?\b", name2)
        if num1 and num2 and num1 != num2:
            return False, name1, name2

        # Direct normalization match
        if norm1 == norm2:
            canonical = name1 if len(name1) <= len(name2) else name2
            alias = name2 if canonical == name1 else name1
            return True, canonical, alias

        # Substring descriptor inclusion (e.g. "BERT" vs "BERT Model")
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        descriptors = {"model", "method", "framework", "dataset", "architecture", "approach", "system", "benchmark"}

        if words1.issubset(words2) and (words2 - words1).issubset(descriptors):
            return True, name1, name2
        if words2.issubset(words1) and (words1 - words2).issubset(descriptors):
            return True, name2, name1

        # Acronym match (e.g. "RAG" vs "Retrieval Augmented Generation")
        acronym1 = "".join(w[0] for w in norm1.split() if w)
        acronym2 = "".join(w[0] for w in norm2.split() if w)
        if (acronym1 == norm2 and len(norm2) <= 5) or (acronym2 == norm1 and len(norm1) <= 5):
            canonical = name2 if len(name2) > len(name1) else name1
            alias = name1 if canonical == name2 else name2
            return True, canonical, alias

        # Strict high similarity cutoff if names are very close
        if sim >= 0.85 and (norm1 in norm2 or norm2 in norm1):
            canonical = name1 if len(name1) <= len(name2) else name2
            alias = name2 if canonical == name1 else name1
            return True, canonical, alias

        return False, name1, name2

    def resolve_entities(self, client: Neo4jGraphClient) -> Dict:
        """Run blocking, adjudication, canonical table building, and graph merging."""
        # Query active entities from Neo4j
        with client.driver.session(database=client.database) as session:
            res = session.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.type AS type")
            entities = [dict(rec) for rec in res]

        before_entity_count = len(entities)
        logger.info(f"Starting Entity Resolution: {before_entity_count} active entity nodes.")

        candidate_pairs = self.block_candidate_pairs(entities)
        canonical_map = self.load_canonical_map()
        merges: List[Tuple[str, str, str]] = []  # (alias_name, canonical_id, canonical_name)

        for e1, e2, sim in candidate_pairs:
            should_merge, canonical_name, alias_name = self.adjudicate_pair(e1, e2, sim)
            if should_merge:
                canonical_id = client.canonical_entity_id(canonical_name)
                entity_type = e1.get("type") or e2.get("type") or "Entity"

                if canonical_id not in canonical_map:
                    canonical_map[canonical_id] = {
                        "canonical_id": canonical_id,
                        "canonical_name": canonical_name,
                        "entity_type": entity_type,
                        "aliases": list(set([canonical_name, alias_name])),
                    }
                else:
                    if alias_name not in canonical_map[canonical_id]["aliases"]:
                        canonical_map[canonical_id]["aliases"].append(alias_name)

                merges.append((alias_name, canonical_id, canonical_name))
                logger.info(f"Merge decision: '{alias_name}' -> '{canonical_name}' (sim: {sim:.3f})")

        self.save_canonical_map(canonical_map)

        # Apply merges into Neo4j
        merged_count = self._apply_merges_to_neo4j(client, merges, canonical_map)

        stats = client.get_graph_stats()
        after_entity_count = stats["entity_nodes"]

        summary = {
            "before_entity_count": before_entity_count,
            "after_entity_count": after_entity_count,
            "total_merges_performed": len(merges),
            "canonical_entities_count": len(canonical_map),
            "sample_merges": [
                {"alias": m[0], "canonical": m[2]} for m in merges[:10]
            ],
        }

        logger.info(
            f"Entity Resolution Complete: Before={before_entity_count}, After={after_entity_count}, Merges={len(merges)}"
        )
        return summary

    def _apply_merges_to_neo4j(
        self, client: Neo4jGraphClient, merges: List[Tuple[str, str, str]], canonical_map: Dict[str, dict]
    ) -> int:
        """Execute Cypher to merge alias nodes under canonical entity nodes using APOC."""
        merged_count = 0
        with client.driver.session(database=client.database) as session:
            for alias_name, cid, c_name in merges:
                if alias_name == c_name:
                    continue

                alias_id = client.canonical_entity_id(alias_name)

                try:
                    res = session.run(
                        """
                        MATCH (c:Entity) WHERE c.id = $cid OR c.name = $c_name
                        MATCH (a:Entity) WHERE (a.name = $alias_name OR a.id = $alias_id) AND elementId(a) <> elementId(c)
                        WITH c, a LIMIT 1
                        CALL apoc.refactor.mergeNodes([c, a], {properties: "override", mergeRels: true}) YIELD node
                        RETURN count(node) AS cnt
                        """,
                        cid=cid,
                        c_name=c_name,
                        alias_name=alias_name,
                        alias_id=alias_id,
                    )
                    if res.single():
                        merged_count += 1
                except Exception as e:
                    logger.warning(f"Merge error for '{alias_name}' -> '{c_name}': {e}")

        return merged_count


def run_50_paper_entity_resolution() -> Dict:
    """Extract triplets across all 50 papers, load into Neo4j, and run Entity Resolution."""
    from extractor.llm_extractor import KnowledgeExtractor

    logger.info("Running Knowledge Extraction across full 50-paper corpus...")
    extractor = KnowledgeExtractor()
    extractor.extract_corpus(num_papers=50)

    with Neo4jGraphClient() as client:
        client.clear_graph()
        client.ingest_from_file()
        
        resolver = EntityResolver()
        summary = resolver.resolve_entities(client)
        return summary


def main():
    summary = run_50_paper_entity_resolution()
    print("\n================ 50-Paper Entity Resolution Summary ================")
    print(f"Before Entity Count: {summary['before_entity_count']}")
    print(f"After Entity Count:  {summary['after_entity_count']}")
    print(f"Total Merges:        {summary['total_merges_performed']}")
    print("\nSample Merges Spot-Check:")
    for i, m in enumerate(summary["sample_merges"], 1):
        print(f"  {i:02d}. '{m['alias']}'  -->  '{m['canonical']}'")


if __name__ == "__main__":
    main()
