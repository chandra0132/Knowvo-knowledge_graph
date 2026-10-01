import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph.neo4j_client import Neo4jGraphClient
from graphrag.config import GraphRAGConfig, config
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vector_index")


class ChunkVectorIndexer:
    """Manages text chunk vector embeddings and native Neo4j vector search."""

    def __init__(self, cfg: Optional[GraphRAGConfig] = None):
        self.cfg = cfg or config
        self._model = None
        self.driver = GraphDatabase.driver(
            self.cfg.neo4j_uri,
            auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
        )
        self.database = self.cfg.neo4j_database

    @property
    def model(self):
        """Lazy load SentenceTransformer model if available."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.cfg.embedding_model_name}")
                self._model = SentenceTransformer(self.cfg.embedding_model_name)
            except (ImportError, Exception) as e:
                logger.debug(f"SentenceTransformer not available ({e}); using text search fallback.")
                self._model = False
        return self._model if self._model is not False else None

    def close(self):
        """Close driver connection."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def setup_vector_index(self):
        """Create native Neo4j vector index if not exists."""
        query = f"""
        CREATE VECTOR INDEX {self.cfg.vector_index_name} IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {{indexConfig: {{`vector.dimensions`: {self.cfg.embedding_dim}, `vector.similarity_function`: "cosine"}}}}
        """
        with self.driver.session(database=self.database) as session:
            try:
                session.run(query)
                logger.info(f"Native Neo4j vector index '{self.cfg.vector_index_name}' initialized.")
            except Exception as e:
                logger.warning(f"Vector index creation notice: {e}")

    def index_all_chunks(self, force_reindex: bool = False, batch_size: int = 128) -> int:
        """Read processed chunk JSON files, compute embeddings, and store in Neo4j."""
        self.setup_vector_index()

        with self.driver.session(database=self.database) as session:
            if not force_reindex:
                count_res = session.run("MATCH (c:Chunk) RETURN count(c) AS cnt").single()
                if count_res and count_res["cnt"] > 0:
                    indexed_cnt = count_res["cnt"]
                    logger.info(f"Found {indexed_cnt} existing Chunk nodes in Neo4j vector index. Skipping re-indexing.")
                    return indexed_cnt

        all_chunks: List[Dict[str, Any]] = []
        json_files = list(self.cfg.processed_dir.glob("*.json"))

        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    chunks = data.get("chunks", [])
                    for ch in chunks:
                        if ch.get("text", "").strip():
                            all_chunks.append({
                                "chunk_id": ch.get("chunk_id", f"{ch.get('paper_id')}_c{ch.get('chunk_index')}"),
                                "paper_id": ch.get("paper_id", "unknown"),
                                "section": ch.get("section", "Unknown"),
                                "text": ch.get("text", "").strip(),
                            })
            except Exception as e:
                logger.error(f"Error reading processed file {jf}: {e}")

        if not all_chunks:
            logger.warning("No chunks found to index.")
            return 0

        logger.info(f"Embedding {len(all_chunks)} text chunks with {self.cfg.embedding_model_name}...")
        texts = [c["text"] for c in all_chunks]
        embeddings = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        for i, c in enumerate(all_chunks):
            c["embedding"] = embeddings[i].tolist()

        logger.info(f"Ingesting {len(all_chunks)} Chunk nodes into Neo4j...")
        total_ingested = 0
        cypher_batch = """
        UNWIND $batch AS item
        MERGE (c:Chunk {id: item.chunk_id})
        SET c.paper_id = item.paper_id,
            c.section = item.section,
            c.text = item.text,
            c.embedding = item.embedding
        MERGE (p:Paper {id: item.paper_id})
        MERGE (c)-[:BELONGS_TO]->(p)
        """

        with self.driver.session(database=self.database) as session:
            for i in range(0, len(all_chunks), batch_size):
                batch = all_chunks[i : i + batch_size]
                session.run(cypher_batch, {"batch": batch})
                total_ingested += len(batch)

        logger.info(f"Successfully indexed {total_ingested} Chunk nodes into Neo4j native vector index.")
        return total_ingested

    def search_similar_chunks(
        self, query_text: str, top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search against Neo4j native vector index or text search fallback."""
        k = top_k or self.cfg.top_k_vector

        # If model is available, perform native vector index search
        if self.model is not None:
            try:
                query_embedding = self.model.encode([query_text], convert_to_numpy=True)[0].tolist()
                cypher = f"""
                CALL db.index.vector.queryNodes('{self.cfg.vector_index_name}', $k, $query_embedding)
                YIELD node, score
                RETURN node.id AS chunk_id,
                       node.paper_id AS paper_id,
                       node.section AS section,
                       node.text AS text,
                       score
                ORDER BY score DESC
                """
                results: List[Dict[str, Any]] = []
                with self.driver.session(database=self.database) as session:
                    res = session.run(cypher, {"k": k, "query_embedding": query_embedding})
                    for record in res:
                        results.append({
                            "chunk_id": record["chunk_id"],
                            "paper_id": record["paper_id"],
                            "section": record["section"],
                            "text": record["text"],
                            "score": float(record["score"]),
                        })
                return results
            except Exception as e:
                logger.debug(f"Native vector search failed ({e}), falling back to text search.")

        # Lightweight fallback: Text search on Neo4j Chunk nodes
        words = [w for w in re.findall(r"\w+", query_text) if len(w) > 3][:5]
        filter_clause = " OR ".join([f"toLower(c.text) CONTAINS toLower($w{i})" for i in range(len(words))]) if words else "1=1"
        params: Dict[str, Any] = {f"w{i}": w for i, w in enumerate(words)}
        params["k"] = k

        cypher_fallback = f"""
        MATCH (c:Chunk)
        WHERE {filter_clause}
        RETURN c.id AS chunk_id,
               c.paper_id AS paper_id,
               c.section AS section,
               c.text AS text,
               0.75 AS score
        LIMIT $k
        """
        results: List[Dict[str, Any]] = []
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run(cypher_fallback, params)
                for record in res:
                    results.append({
                        "chunk_id": record["chunk_id"],
                        "paper_id": record["paper_id"],
                        "section": record["section"],
                        "text": record["text"],
                        "score": float(record["score"]),
                    })
        except Exception as e:
            logger.debug(f"Chunk text search error: {e}")

        return results


def main():
    with ChunkVectorIndexer() as indexer:
        count = indexer.index_all_chunks()
        hits = indexer.search_similar_chunks("mitigate hallucination in RAG", top_k=3)
        print(f"Total Chunks Indexed: {count}")
        print(f"Top 3 Hits for 'mitigate hallucination in RAG':")
        for h in hits:
            print(f"  [{h['score']:.4f}] Paper {h['paper_id']} ({h['section']}): {h['text'][:100]}...")


if __name__ == "__main__":
    main()
