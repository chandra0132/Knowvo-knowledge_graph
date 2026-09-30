import logging
import re
from typing import Any, Dict, List, Optional

from graph.neo4j_client import Neo4jGraphClient
from verification.config import VerificationConfig, config
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("graph_updater")


class GraphVerificationUpdater:
    """Applies verification outcomes directly into the Neo4j Knowledge Graph."""

    def __init__(self, cfg: Optional[VerificationConfig] = None):
        self.cfg = cfg or config
        self.driver = GraphDatabase.driver(
            self.cfg.neo4j_uri,
            auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
        )
        self.database = self.cfg.neo4j_database

    def close(self):
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _canonical_entity_id(self, name: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip()).strip("_").lower()
        return f"ent_{clean}" if clean else "ent_unknown"

    def _clean_rel_type(self, triplet: Dict[str, Any]) -> str:
        rel = triplet.get("relation", "RELATED_TO")
        cand = triplet.get("candidate_relation")
        if rel in ["OTHER", "CoreRelation.OTHER"] and cand:
            clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(cand).strip().upper())
            return clean if clean else "RELATED_TO"
        if str(rel).startswith("CoreRelation."):
            rel = str(rel).split(".")[-1]
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(rel).strip().upper())
        return clean if clean else "RELATED_TO"

    def apply_verification_results(
        self, verification_results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Update Neo4j relationships based on CONFIRMED, CORRECTED, or REJECTED statuses."""
        stats = {"confirmed": 0, "corrected": 0, "rejected": 0}

        with self.driver.session(database=self.database) as session:
            for item in verification_results:
                status = item.get("status")
                orig = item.get("original_triplet", {})
                orig_subj = str(orig.get("subject", "")).strip()
                orig_obj = str(orig.get("object", "")).strip()
                orig_paper_id = orig.get("paper_id", "unknown")

                if not orig_subj or not orig_obj:
                    continue

                if status == "CONFIRMED":
                    # Mark edge as verified and boost confidence
                    cypher = """
                    MATCH (s:Entity)-[r]->(o:Entity)
                    WHERE toLower(s.name) = toLower($subj)
                      AND toLower(o.name) = toLower($obj)
                      AND r.paper_id = $paper_id
                    SET r.verified = true, r.confidence = 0.95
                    RETURN count(r) AS updated
                    """
                    res = session.run(
                        cypher,
                        {"subj": orig_subj, "obj": orig_obj, "paper_id": orig_paper_id},
                    )
                    stats["confirmed"] += 1

                elif status == "REJECTED":
                    # Delete invalid edge from graph
                    cypher = """
                    MATCH (s:Entity)-[r]->(o:Entity)
                    WHERE toLower(s.name) = toLower($subj)
                      AND toLower(o.name) = toLower($obj)
                      AND r.paper_id = $paper_id
                    DELETE r
                    RETURN count(r) AS deleted
                    """
                    session.run(
                        cypher,
                        {"subj": orig_subj, "obj": orig_obj, "paper_id": orig_paper_id},
                    )
                    stats["rejected"] += 1

                elif status == "CORRECTED":
                    corrected = item.get("corrected_triplet")
                    if not corrected:
                        continue

                    # 1. Delete old inaccurate edge
                    cypher_del = """
                    MATCH (s:Entity)-[r]->(o:Entity)
                    WHERE toLower(s.name) = toLower($subj)
                      AND toLower(o.name) = toLower($obj)
                      AND r.paper_id = $paper_id
                    DELETE r
                    """
                    session.run(
                        cypher_del,
                        {"subj": orig_subj, "obj": orig_obj, "paper_id": orig_paper_id},
                    )

                    # 2. Insert corrected edge
                    new_subj = str(corrected.get("subject", orig_subj)).strip()
                    new_obj = str(corrected.get("object", orig_obj)).strip()
                    new_rel = self._clean_rel_type(corrected)

                    params = {
                        "subj_id": self._canonical_entity_id(new_subj),
                        "subj_name": new_subj,
                        "subj_type": corrected.get("subject_type", "Entity"),
                        "obj_id": self._canonical_entity_id(new_obj),
                        "obj_name": new_obj,
                        "obj_type": corrected.get("object_type", "Entity"),
                        "paper_id": corrected.get("paper_id", orig_paper_id),
                        "rel_type": new_rel,
                        "props": {
                            "paper_id": corrected.get("paper_id", orig_paper_id),
                            "section": corrected.get("section", "Unknown"),
                            "evidence_span": corrected.get("evidence_span", ""),
                            "confidence": float(corrected.get("confidence", 0.95)),
                            "verified": True,
                            "corrected": True,
                        },
                    }

                    cypher_insert = """
                    MERGE (s:Entity {id: $subj_id})
                    ON CREATE SET s.name = $subj_name, s.type = $subj_type
                    MERGE (o:Entity {id: $obj_id})
                    ON CREATE SET o.name = $obj_name, o.type = $obj_type
                    MERGE (p:Paper {id: $paper_id})

                    MERGE (s)-[:MENTIONED_IN]->(p)
                    MERGE (o)-[:MENTIONED_IN]->(p)

                    WITH s, o, $rel_type AS rtype, $props AS props
                    CALL apoc.create.relationship(s, rtype, props, o) YIELD rel
                    RETURN type(rel) AS created_rel
                    """
                    try:
                        session.run(cypher_insert, params)
                        stats["corrected"] += 1
                    except Exception as e:
                        logger.error(f"Failed to insert corrected relationship: {e}")

        logger.info(f"Graph verification updates applied: {stats}")
        return stats


def main():
    with GraphVerificationUpdater() as updater:
        sample_results = [
            {
                "status": "CONFIRMED",
                "original_triplet": {
                    "subject": "BERT",
                    "object": "Transformer",
                    "paper_id": "1908.08962",
                },
            }
        ]
        res = updater.apply_verification_results(sample_results)
        print("Updated Graph:", res)


if __name__ == "__main__":
    main()
