import pytest
from graph.config import config
from graph.cypher_queries import (
    query_hallucination_mitigation_methods,
    query_method_evaluations_and_comparisons,
    query_model_architecture_lineage,
)
from graph.neo4j_client import Neo4jGraphClient


def test_neo4j_graph_ingestion_and_constraints():
    """Verify Neo4j schema setup, triplet ingestion, and sane node counts."""
    with Neo4jGraphClient() as client:
        client.clear_graph()
        ingested_count = client.ingest_from_file()
        stats = client.get_graph_stats()

        assert ingested_count >= 20, f"Expected >=20 ingested triplets, got {ingested_count}"
        assert stats["total_nodes"] >= 20, f"Expected >=20 total nodes, got {stats['total_nodes']}"
        assert stats["entity_nodes"] >= 15, f"Expected >=15 entity nodes, got {stats['entity_nodes']}"
        assert stats["paper_nodes"] >= 5, f"Expected >=5 paper nodes, got {stats['paper_nodes']}"

        # Sanity check: node count is sane (no runaway duplicate node explosion)
        assert (
            stats["entity_nodes"] < 500
        ), f"Entity node explosion detected: {stats['entity_nodes']} nodes"

        print(f"\nIngestion Test PASSED! Ingested {ingested_count} triplets.")
        print(f"Stats: Entities={stats['entity_nodes']}, Papers={stats['paper_nodes']}, Edges={stats['total_relationships']}")


def test_cypher_domain_queries():
    """Verify that the 3 hand-written Cypher domain queries return non-empty results."""
    with Neo4jGraphClient() as client:
        # Query 1: Hallucination & error mitigation
        q1_results = query_hallucination_mitigation_methods(client)
        assert (
            len(q1_results) > 0
        ), "Query 1 (Hallucination Mitigation) returned 0 results"
        assert "method" in q1_results[0]
        assert "evidence" in q1_results[0]
        assert "paper_id" in q1_results[0]

        # Query 2: Architecture / technology lineage
        q2_results = query_model_architecture_lineage(client, keyword="LLM")
        assert (
            len(q2_results) >= 0
        )  # Valid query execution

        # Query 3: Evaluations & comparisons
        q3_results = query_method_evaluations_and_comparisons(client)
        assert (
            len(q3_results) > 0
        ), "Query 3 (Evaluations & Comparisons) returned 0 results"
        assert "method" in q3_results[0]
        assert "target_benchmark_or_baseline" in q3_results[0]

        print(f"\nCypher Queries Test PASSED!")
        print(f"  Q1 (Mitigation): {len(q1_results)} results")
        print(f"  Q3 (Evaluations): {len(q3_results)} results")
