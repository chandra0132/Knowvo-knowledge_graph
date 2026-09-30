from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessorConfig(BaseSettings):
    # Chunking & Cleaning Settings
    max_chunk_char_size: int = 2500  # split sections longer than ~2500 chars
    min_chunk_char_size: int = 100   # filter out tiny artifact chunks

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    raw_pdfs_dir: Path = base_dir / "data" / "raw_pdfs"
    processed_dir: Path = base_dir / "data" / "processed"
    manifest_file: Path = base_dir / "data" / "corpus.jsonl"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        """Ensure output directory exists."""
        self.processed_dir.mkdir(parents=True, exist_ok=True)


config = ProcessorConfig()
