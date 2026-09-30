import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_api_health():
    """Verify health check endpoint returns 200 and healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data


def test_api_stats():
    """Verify stats endpoint returns graph node and relationship metrics."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_nodes" in data
    assert "entity_nodes" in data
    assert "paper_nodes" in data
    assert "total_relationships" in data
    assert data["total_nodes"] > 0
    assert data["paper_nodes"] >= 10


def test_api_graph_explore():
    """Verify graph exploration endpoint returns nodes and links for visualization."""
    response = client.get("/api/graph/explore?limit=20")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) > 0
    assert len(data["links"]) > 0

    first_node = data["nodes"][0]
    assert "id" in first_node
    assert "label" in first_node

    first_link = data["links"][0]
    assert "source" in first_link
    assert "target" in first_link
    assert "relation" in first_link


def test_api_query():
    """Verify natural language query endpoint returns answer, citations, and reasoning path."""
    payload = {
        "question": "How do recent methods mitigate LLM hallucination in QA or RAG tasks?",
        "top_k_vector": 3,
        "top_k_graph": 3,
    }
    response = client.post("/api/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "question" in data
    assert "answer" in data
    assert len(data["answer"]) > 10
    assert "cited_papers" in data
    assert "reasoning_path" in data
    assert "latency_sec" in data
    assert data["latency_sec"] >= 0.0
