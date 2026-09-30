import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from graph.config import GraphConfig, config
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("neo4j_client")


class Neo4jGraphClient:
    """Neo4j Client for knowledge graph ingestion, schema management, and querying."""

    def __init__(self, cfg: Optional[GraphConfig] = None):
        self.cfg = cfg or config
        self.driver = GraphDatabase.driver(
            self.cfg.neo4j_uri,
            auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
        )
        self.database = self.cfg.neo4j_database

    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def canonical_entity_id(self, name: str) -> str:
        """Create a clean, normalized canonical ID string from an entity name."""
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
        return f"ent_{clean}" if clean else "ent_unknown"

    def setup_schema_constraints(self):
        """Create uniqueness constraints and indexes in Neo4j."""
        queries = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE CONSTRAINT paper_id_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
        ]

        with self.driver.session(database=self.database) as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    logger.warning(f"Constraint setup query warning: {e}")
        logger.info("Neo4j schema constraints and indexes initialized successfully.")

    def clear_graph(self):
        """Clear all nodes and relationships from the active database."""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Cleared all nodes and relationships from Neo4j database.")

    def _clean_rel_type(self, triplet: dict) -> str:
        """Determine relationship label string for Cypher."""
        rel = triplet.get("relation", "OTHER")
        cand_rel = triplet.get("candidate_relation")

        if rel == "OTHER" or rel == "CoreRelation.OTHER":
            if cand_rel:
                clean_rel = re.sub(r"[^a-zA-Z0-9_]+", "_", str(cand_rel).strip().upper())
                return clean_rel if clean_rel else "RELATED_TO"
            return "RELATED_TO"
        
        # Strip enum prefix if present
        if str(rel).startswith("CoreRelation."):
            rel = str(rel).split(".")[-1]
            
        clean_rel = re.sub(r"[^a-zA-Z0-9_]+", "_", str(rel).strip().upper())
        return clean_rel if clean_rel else "RELATED_TO"

    def ingest_triplets_batch(self, triplets: List[dict]) -> int:
        """Ingest a list of extracted triplets into Neo4j."""
        self.setup_schema_constraints()

        ingested_count = 0
        with self.driver.session(database=self.database) as session:
            for t in triplets:
                subj_name = t["subject"].strip()
                obj_name = t["object"].strip()
                if not subj_name or not obj_name:
                    continue

                subj_id = self.canonical_entity_id(subj_name)
                obj_id = self.canonical_entity_id(obj_name)
                rel_type = self._clean_rel_type(t)

                params = {
                    "subj_id": subj_id,
                    "subj_name": subj_name,
                    "subj_type": t.get("subject_type", "Entity"),
                    "obj_id": obj_id,
                    "obj_name": obj_name,
                    "obj_type": t.get("object_type", "Entity"),
                    "paper_id": t.get("paper_id", "unknown"),
                    "rel_type": rel_type,
                    "props": {
                        "paper_id": t.get("paper_id", "unknown"),
                        "section": t.get("section", "unknown"),
                        "evidence_span": t.get("evidence_span", ""),
                        "confidence": float(t.get("confidence", 0.9)),
                        "chunk_id": t.get("chunk_id", ""),
                    },
                }

                cypher = """
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
                    session.run(cypher, params)
                    ingested_count += 1
                except Exception as e:
                    logger.error(f"Failed to ingest triplet ({subj_name})->[{rel_type}]->({obj_name}): {e}")

        logger.info(f"Successfully ingested {ingested_count} triplets into Neo4j graph.")
        return ingested_count

    def ingest_from_file(self, triplets_file_path: Optional[Path] = None) -> int:
        """Ingest all triplets from all_triplets.jsonl or individual paper extraction files."""
        target_path = triplets_file_path or self.cfg.all_triplets_file
        triplets: List[dict] = []

        if target_path.exists():
            with open(target_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        triplets.append(json.loads(line))
        else:
            # Fallback to reading files in extractions_dir
            for json_file in self.cfg.extractions_dir.glob("*.json"):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    triplets.extend(data.get("triplets", []))

        logger.info(f"Loaded {len(triplets)} triplets for ingestion into Neo4j.")
        return self.ingest_triplets_batch(triplets)

    def get_graph_stats(self) -> Dict:
        """Query Neo4j for node, edge, and label counts."""
        with self.driver.session(database=self.database) as session:
            total_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            entities = session.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
            papers = session.run("MATCH (p:Paper) RETURN count(p) AS c").single()["c"]
            relationships = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            
            rel_types_res = session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS t")
            rel_types = [rec["t"] for rec in rel_types_res]

        stats = {
            "total_nodes": total_nodes,
            "entity_nodes": entities,
            "paper_nodes": papers,
            "total_relationships": relationships,
            "relationship_types": rel_types,
        }
        return stats


def main():
    with Neo4jGraphClient() as graph:
        graph.clear_graph()
        ingested = graph.ingest_from_file()
        stats = graph.get_graph_stats()
        print(f"\nGraph Ingestion Complete! Ingested {ingested} triplets.")
        print(f"Graph Stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
