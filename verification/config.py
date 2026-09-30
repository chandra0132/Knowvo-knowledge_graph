from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VerificationConfig(BaseSettings):
    """Configuration settings for Verification and Self-Improvement Loop."""

    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"
    neo4j_database: str = "neo4j"

    # LLM Settings
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_model: str = "gemini-2.5-flash"

    # Verification Thresholds
    confidence_threshold: float = 0.70

    # Data Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    all_triplets_file: Path = base_dir / "data" / "all_triplets.jsonl"
    flagged_triplets_file: Path = base_dir / "data" / "flagged_triplets.jsonl"
    verification_results_file: Path = base_dir / "data" / "verification_results.jsonl"
    dynamic_examples_file: Path = base_dir / "data" / "dynamic_few_shot_examples.json"
    processed_dir: Path = base_dir / "data" / "processed"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self):
        """Ensure necessary data directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


config = VerificationConfig()
