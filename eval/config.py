from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EvalConfig(BaseSettings):
    """Configuration settings for Phase 8 Evaluation Layer."""

    # File Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    benchmark_dir: Path = base_dir / "data" / "benchmark"
    qa_benchmark_file: Path = benchmark_dir / "qa_benchmark.json"
    labeled_extraction_file: Path = benchmark_dir / "labeled_extraction_subset.json"
    evaluation_report_json: Path = benchmark_dir / "evaluation_report.json"
    evaluation_report_md: Path = benchmark_dir / "evaluation_report.md"

    # LLM Settings
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_model: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self):
        """Ensure benchmark data directories exist."""
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)


config = EvalConfig()
