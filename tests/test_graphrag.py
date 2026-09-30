import pytest
from graphrag.config import config
from graphrag.engine import GraphRAGEngine
from graphrag.evidence_fusion import EvidenceFusor
from graphrag.query_analyzer import QueryAnalysisResult, QueryAnalyzer
from graphrag.vector_index import ChunkVectorIndexer


def test_chunk_vector_indexer():
    """Verify text chunk vector indexing and native Neo4j vector search."""
    with ChunkVectorIndexer() as indexer:
        indexed_count = indexer.index_all_chunks()
        assert indexed_count > 100, f"Expected >100 chunks indexed, got {indexed_count}"

        hits = indexer.search_similar_chunks("hallucination mitigation RAG", top_k=3)
        assert len(hits) == 3, f"Expected 3 vector search hits, got {len(hits)}"
        assert "chunk_id" in hits[0]
        assert "paper_id" in hits[0]
        assert "text" in hits[0]
        assert hits[0]["score"] > 0.3, f"Low similarity score: {hits[0]['score']}"


def test_query_analyzer_and_graph_traversal():
    """Verify natural language query analysis and Cypher graph traversal."""
    with QueryAnalyzer() as analyzer:
        question = "Which models build on or extend the Transformer architecture?"
        analysis: QueryAnalysisResult = analyzer.analyze_query(question)

        assert len(analysis.entities) > 0 or len(analysis.relations) > 0
        
        paths = analyzer.traverse_graph(analysis, top_k=5)
        assert len(paths) > 0, "Graph traversal returned 0 paths"
        assert "subject" in paths[0]
        assert "relation" in paths[0]
        assert "object" in paths[0]


def test_evidence_fusion():
    """Verify fusion of graph paths and vector hits into structured context."""
    fusor = EvidenceFusor()
    sample_graph = [
        {
            "subject": "Transformer",
            "relation": "EXTENDS",
            "object": "LLM Architecture",
            "paper_id": "2608.01234v1",
            "confidence": 0.92,
            "evidence_span": "We extend Transformer architecture.",
        }
    ]
    sample_vector = [
        {
            "chunk_id": "chunk_99",
            "paper_id": "2608.01234v1",
            "section": "Methods",
            "text": "Transformer based models demonstrate superior scaling.",
            "score": 0.85,
        }
    ]

    fused = fusor.fuse(sample_graph, sample_vector)
    assert fused.graph_triplet_count == 1
    assert fused.vector_hit_count == 1
    assert "2608.01234v1" in fused.cited_papers
    assert len(fused.reasoning_paths) == 1
    assert "KNOWLEDGE GRAPH PATHS" in fused.context_text
    assert "RELEVANT TEXT CHUNKS" in fused.context_text


@pytest.mark.parametrize(
    "question",
    [
        "How do recent methods mitigate LLM hallucination in QA or RAG tasks?",
        "Which models build on or extend the Transformer architecture?",
        "What datasets or benchmarks are used to evaluate factuality and hallucination?",
        "How does CoAL-RAG or DexterSQL improve baseline retrieval/Text-to-SQL performance?",
        "What are the main causes or categories of hallucinations identified in the corpus?",
    ],
)
def test_graphrag_5_example_questions(question: str):
    """Verify that each of the 5 example questions returns a sensible answer, cited papers, and reasoning path."""
    with GraphRAGEngine() as engine:
        result = engine.query(question, top_k_vector=5, top_k_graph=5)

        assert result["question"] == question
        assert isinstance(result["answer"], str) and len(result["answer"]) > 20
        assert isinstance(result["cited_papers"], list) and len(result["cited_papers"]) > 0
        assert isinstance(result["reasoning_path"], list) and len(result["reasoning_path"]) > 0

        # Check evidence grounding
        fused = result["fused_evidence"]
        assert fused["graph_triplet_count"] > 0 or fused["vector_hit_count"] > 0

        print(f"\n[Passed Question Test]: {question}")
        print(f"  Cited Papers ({len(result['cited_papers'])}): {result['cited_papers'][:3]}")
        print(f"  Reasoning Path Step 1: {result['reasoning_path'][0]}")
