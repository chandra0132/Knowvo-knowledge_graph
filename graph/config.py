from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphConfig(BaseSettings):
    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"
    neo4j_database: str = "neo4j"

    # File Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    extractions_dir: Path = base_dir / "data" / "extractions"
    all_triplets_file: Path = base_dir / "data" / "all_triplets.jsonl"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = GraphConfig()
