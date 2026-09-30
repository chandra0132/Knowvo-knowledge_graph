import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractorConfig(BaseSettings):
    # LLM & API Settings
    llm_api_key: str = "your_llm_api_key_here"
    llm_model: str = "gemini-2.5-flash"
    
    # Langfuse Tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    processed_dir: Path = base_dir / "data" / "processed"
    extractions_dir: Path = base_dir / "data" / "extractions"
    candidate_relations_file: Path = base_dir / "data" / "candidate_relations.jsonl"
    all_triplets_file: Path = base_dir / "data" / "all_triplets.jsonl"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        """Ensure extractions directory exists."""
        self.extractions_dir.mkdir(parents=True, exist_ok=True)


config = ExtractorConfig()
