import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorConfig(BaseSettings):
    # Search & Domain Configuration (LLM Hallucination Research)
    arxiv_search_query: str = (
        'cat:cs.CL AND (hallucination OR "factuality in LLMs" OR "hallucination detection")'
    )
    arxiv_max_results: int = 40  # V0 scope: 30-50 papers
    arxiv_rate_limit_delay: float = 3.0  # seconds between downloads

    # Directory Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    raw_pdfs_dir: Path = base_dir / "data" / "raw_pdfs"
    cache_dir: Path = base_dir / "data" / "cache"
    manifest_file: Path = base_dir / "data" / "corpus.jsonl"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        """Create required data directories if they do not exist."""
        self.raw_pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


config = CollectorConfig()
