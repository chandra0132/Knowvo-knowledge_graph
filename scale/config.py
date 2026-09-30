import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScaleConfig(BaseSettings):
    """Configuration for Phase 10 Scaled Corpus Execution (500 to 5,000 papers)."""

    # Model Tiering Configuration
    cheap_model: str = "gemini-2.5-flash"
    expensive_model: str = "gemini-2.5-pro"
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")

    # Pricing per 1M tokens (USD)
    # Gemini 2.5 Flash: $0.075 / 1M input, $0.30 / 1M output
    cheap_input_cost_per_1m: float = 0.075
    cheap_output_cost_per_1m: float = 0.30

    # Gemini 2.5 Pro: $1.25 / 1M input, $5.00 / 1M output
    expensive_input_cost_per_1m: float = 1.25
    expensive_output_cost_per_1m: float = 5.00

    # Concurrency and Retry Settings
    max_concurrency: int = 15
    max_retries: int = 4
    initial_retry_delay_sec: float = 0.5
    max_retry_delay_sec: float = 10.0
    backoff_factor: float = 2.0

    # Scale Run Target
    target_papers: int = 500
    batch_size: int = 25
    confidence_flag_threshold: float = 0.70

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    processed_dir: Path = base_dir / "data" / "processed"
    extractions_dir: Path = base_dir / "data" / "extractions"
    all_triplets_file: Path = base_dir / "data" / "all_triplets.jsonl"
    flagged_triplets_file: Path = base_dir / "data" / "flagged_triplets.jsonl"
    verification_results_file: Path = base_dir / "data" / "verification_results.jsonl"
    checkpoint_file: Path = base_dir / "data" / "scale_checkpoint.json"
    cost_report_file: Path = base_dir / "data" / "cost_report.json"
    cost_summary_md: Path = base_dir / "data" / "cost_summary.md"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_directories(self):
        """Ensure all required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.extractions_dir.mkdir(parents=True, exist_ok=True)


config = ScaleConfig()
