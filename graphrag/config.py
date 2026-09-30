from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphRAGConfig(BaseSettings):
    """Configuration settings for GraphRAG Engine."""

    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"
    neo4j_database: str = "neo4j"

    # LLM Settings
    gemini_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_model: str = "gemini-2.5-flash"

    # Embedding & Vector Index Settings
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    vector_index_name: str = "chunk_embeddings"

    # Retrieval Settings
    top_k_vector: int = 5
    top_k_graph: int = 10
    confidence_threshold: float = 0.5

    # Data Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    processed_dir: Path = base_dir / "data" / "processed"
    extractions_dir: Path = base_dir / "data" / "extractions"
    all_triplets_file: Path = base_dir / "data" / "all_triplets.jsonl"
    canonical_entities_file: Path = base_dir / "data" / "canonical_entities.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = GraphRAGConfig()
