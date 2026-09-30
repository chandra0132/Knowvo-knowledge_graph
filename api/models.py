from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request payload for asking a question to the GraphRAG engine."""

    question: str = Field(
        ...,
        min_length=3,
        description="The natural-language question to ask.",
        examples=["How do recent methods mitigate LLM hallucination in QA or RAG tasks?"],
    )
    top_k_vector: Optional[int] = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of text chunks to retrieve via vector search.",
    )
    top_k_graph: Optional[int] = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of graph paths to traverse from the knowledge graph.",
    )


class QueryResponse(BaseModel):
    """Response payload containing generated answer, citations, and reasoning path."""

    question: str
    answer: str
    cited_papers: List[str] = Field(default_factory=list)
    reasoning_path: List[str] = Field(default_factory=list)
    graph_paths: List[Dict[str, Any]] = Field(default_factory=list)
    vector_hits: List[Dict[str, Any]] = Field(default_factory=list)
    latency_sec: float


class GraphStatsResponse(BaseModel):
    """Graph statistics response."""

    total_nodes: int
    entity_nodes: int
    paper_nodes: int
    total_relationships: int
    relationship_types: List[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    """Node item for interactive graph visualization."""

    id: str
    label: str
    type: str = "Entity"
    size: float = 8.0


class GraphLink(BaseModel):
    """Link item for interactive graph visualization."""

    source: str
    target: str
    relation: str
    paper_id: Optional[str] = None
    confidence: Optional[float] = None


class GraphDataResponse(BaseModel):
    """Graph structure response for visualization."""

    nodes: List[GraphNode]
    links: List[GraphLink]
