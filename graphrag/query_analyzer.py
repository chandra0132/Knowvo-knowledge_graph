import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from graphrag.config import GraphRAGConfig, config
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("query_analyzer")


class QueryAnalysisResult(BaseModel):
    """Structured analysis result for a natural language user query."""

    entities: List[str] = Field(
        default_factory=list,
        description="Key entities, concepts, frameworks, models, or benchmarks extracted from the question.",
    )
    relations: List[str] = Field(
        default_factory=list,
        description="Target graph relationship types (e.g. PROPOSES, USES, BUILDS_ON, IMPROVES, CONTRADICTS, EVALUATES, AUTHORED_BY, CITES, EXTENDS, COMPARED_WITH).",
    )
    intent: str = Field(
        default="",
        description="Summary of the user's intent or primary topic of interest.",
    )
    cypher_query: Optional[str] = Field(
        default=None,
        description="Suggested custom Cypher query for graph traversal, if applicable.",
    )


class QueryAnalyzer:
    """Analyzes natural language questions into query intent and executes Neo4j graph traversals."""

    def __init__(self, cfg: Optional[GraphRAGConfig] = None):
        self.cfg = cfg or config
        self.genai_client = self._init_genai_client()
        self.driver = GraphDatabase.driver(
            self.cfg.neo4j_uri,
            auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
        )
        self.database = self.cfg.neo4j_database
        self.canonical_map = self._load_canonical_map()

    def close(self):
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _init_genai_client(self):
        if self.cfg.gemini_api_key and self.cfg.gemini_api_key != "your_llm_api_key_here":
            try:
                from google import genai

                client = genai.Client(api_key=self.cfg.gemini_api_key)
                logger.info(f"Google GenAI client initialized for QueryAnalyzer ({self.cfg.llm_model}).")
                return client
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client in QueryAnalyzer: {e}")
        return None

    def _load_canonical_map(self) -> Dict[str, Dict]:
        if self.cfg.canonical_entities_file.exists():
            try:
                with open(self.cfg.canonical_entities_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load canonical_entities.json: {e}")
        return {}

    def analyze_query(self, question: str) -> QueryAnalysisResult:
        """Decompose natural language question into entities, relations, and intent."""
        if self.genai_client:
            prompt = f"""
            You are a Knowledge Graph Query Analyzer for a scientific paper corpus on LLMs, RAG, and Hallucinations.
            Analyze the following question and extract key entities, concepts, target relations, and intent.

            Question: "{question}"

            Available Graph Relations:
            PROPOSES, USES, BUILDS_ON, IMPROVES, CONTRADICTS, EVALUATES, AUTHORED_BY, CITES, EXTENDS, COMPARED_WITH.

            Return JSON matching the schema.
            """
            try:
                from google.genai import types

                response = self.genai_client.models.generate_content(
                    model=self.cfg.llm_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=QueryAnalysisResult,
                        temperature=0.0,
                    ),
                )
                if response.text:
                    parsed = json.loads(response.text)
                    return QueryAnalysisResult(**parsed)
            except Exception as e:
                logger.warning(f"LLM query analysis failed, falling back to rule-based: {e}")

        # Rule-based fallback extraction
        words = re.findall(r"\b[A-Za-z0-9\-\_]{3,}\b", question)
        stop_words = {"what", "how", "which", "does", "the", "and", "for", "are", "used", "recent", "main", "from", "with"}
        entities = [w for w in words if w.lower() not in stop_words]

        relations = []
        q_upper = question.upper()
        if "MITIGATE" in q_upper or "IMPROVE" in q_upper or "REDUCE" in q_upper:
            relations.extend(["IMPROVES", "PROPOSES", "USES"])
        if "BUILD" in q_upper or "EXTEND" in q_upper or "ARCHITECTURE" in q_upper:
            relations.extend(["BUILDS_ON", "EXTENDS", "USES"])
        if "BENCHMARK" in q_upper or "DATASET" in q_upper or "EVALUATE" in q_upper:
            relations.extend(["EVALUATES", "COMPARED_WITH", "USES"])

        return QueryAnalysisResult(
            entities=entities[:5],
            relations=list(set(relations)),
            intent=f"Retrieve knowledge graph paths related to: {question}",
        )

    def traverse_graph(
        self, query_analysis: QueryAnalysisResult, top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Traverse Neo4j graph for paths matching query entities or relations."""
        k = top_k or self.cfg.top_k_graph
        entities = [e.lower().strip() for e in query_analysis.entities if e.strip()]

        cypher_entity_match = """
        MATCH (s:Entity)-[r]->(o:Entity)
        WHERE type(r) <> 'MENTIONED_IN' AND type(r) <> 'BELONGS_TO'
          AND (
            ANY(e IN $entities WHERE toLower(s.name) CONTAINS e OR toLower(o.name) CONTAINS e OR toLower(s.id) CONTAINS e OR toLower(o.id) CONTAINS e)
            OR (size($relations) > 0 AND type(r) IN $relations)
          )
        RETURN s.name AS subject,
               s.type AS subject_type,
               type(r) AS relation,
               o.name AS object,
               o.type AS object_type,
               r.paper_id AS paper_id,
               r.section AS section,
               r.confidence AS confidence,
               r.evidence_span AS evidence_span
        ORDER BY r.confidence DESC
        LIMIT $k
        """

        cypher_fallback = """
        MATCH (s:Entity)-[r]->(o:Entity)
        WHERE type(r) <> 'MENTIONED_IN' AND type(r) <> 'BELONGS_TO'
        RETURN s.name AS subject,
               s.type AS subject_type,
               type(r) AS relation,
               o.name AS object,
               o.type AS object_type,
               r.paper_id AS paper_id,
               r.section AS section,
               r.confidence AS confidence,
               r.evidence_span AS evidence_span
        ORDER BY r.confidence DESC
        LIMIT $k
        """

        results: List[Dict[str, Any]] = []
        with self.driver.session(database=self.database) as session:
            if entities or query_analysis.relations:
                res = session.run(
                    cypher_entity_match,
                    {
                        "entities": entities,
                        "relations": query_analysis.relations,
                        "k": k,
                    },
                )
                for record in res:
                    results.append(dict(record))

            if len(results) < 3:
                res_fb = session.run(cypher_fallback, {"k": k})
                for record in res_fb:
                    d = dict(record)
                    if d not in results:
                        results.append(d)

        return results[:k]


def main():
    with QueryAnalyzer() as analyzer:
        res = analyzer.analyze_query("How do recent methods mitigate LLM hallucination in QA or RAG tasks?")
        print("Query Analysis:", res.model_dump())
        paths = analyzer.traverse_graph(res, top_k=5)
        print(f"Traversed {len(paths)} Graph Paths:")
        for p in paths:
            print(f"  [{p['subject']}] -{p['relation']}-> [{p['object']}] (Paper: {p['paper_id']})")


if __name__ == "__main__":
    main()
