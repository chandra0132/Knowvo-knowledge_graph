import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from scale.config import ScaleConfig, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cost_tracker")


class StageMetrics(BaseModel):
    """Token and cost metrics for a specific pipeline stage."""

    stage_name: str
    model_name: str
    tier: str  # "CHEAP" or "EXPENSIVE" or "LOCAL"
    items_processed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_sec: float = 0.0
    retries_count: int = 0
    errors_count: int = 0


class CostReport(BaseModel):
    """Aggregated cost and performance report across all scale pipeline stages."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    target_corpus_size: int = 500
    papers_processed: int = 0
    total_chunks: int = 0
    total_triplets_extracted: int = 0
    total_triplets_flagged: int = 0
    total_triplets_verified: int = 0
    flagged_ratio_pct: float = 0.0

    # Token and Cost Totals
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Counterfactual comparison (if 100% expensive model was used for everything)
    baseline_all_expensive_cost_usd: float = 0.0
    cost_savings_usd: float = 0.0
    cost_reduction_pct: float = 0.0

    # Pipeline Performance
    total_wall_clock_sec: float = 0.0
    throughput_papers_per_sec: float = 0.0
    throughput_tokens_per_sec: float = 0.0
    average_cost_per_paper_usd: float = 0.0

    # Stage breakdown
    stages: Dict[str, StageMetrics] = Field(default_factory=dict)


class CostTracker:
    """Tracks token consumption, latency, and costs across tiered LLM stages."""

    def __init__(self, cfg: Optional[ScaleConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()
        self.start_time = time.perf_counter()
        self.stages: Dict[str, StageMetrics] = {
            "extraction_tier1": StageMetrics(
                stage_name="Extraction (Tier 1 Cheap)",
                model_name=self.cfg.cheap_model,
                tier="CHEAP",
            ),
            "verification_tier2": StageMetrics(
                stage_name="Verification (Tier 2 Expensive - Flagged Only)",
                model_name=self.cfg.expensive_model,
                tier="EXPENSIVE",
            ),
            "entity_resolution": StageMetrics(
                stage_name="Canonical Entity Resolution",
                model_name="all-MiniLM-L6-v2 + LLM Adjudication",
                tier="LOCAL",
            ),
            "graph_indexing": StageMetrics(
                stage_name="Neo4j Graph & Vector Indexing",
                model_name="all-MiniLM-L6-v2 (384-d)",
                tier="LOCAL",
            ),
        }

    def record_extraction(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        duration_sec: float = 0.0,
        retries: int = 0,
        errors: int = 0,
        chunks_count: int = 1,
    ):
        """Record usage from Tier 1 cheap model extraction."""
        stage = self.stages["extraction_tier1"]
        stage.items_processed += chunks_count
        stage.prompt_tokens += prompt_tokens
        stage.completion_tokens += completion_tokens
        stage.total_tokens += prompt_tokens + completion_tokens
        stage.duration_sec += duration_sec
        stage.retries_count += retries
        stage.errors_count += errors

        # Calculate cost
        cost_in = (prompt_tokens / 1_000_000) * self.cfg.cheap_input_cost_per_1m
        cost_out = (completion_tokens / 1_000_000) * self.cfg.cheap_output_cost_per_1m
        stage.cost_usd += cost_in + cost_out

    def record_verification(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        duration_sec: float = 0.0,
        retries: int = 0,
        errors: int = 0,
        triplets_count: int = 1,
    ):
        """Record usage from Tier 2 expensive model verification on flagged items."""
        stage = self.stages["verification_tier2"]
        stage.items_processed += triplets_count
        stage.prompt_tokens += prompt_tokens
        stage.completion_tokens += completion_tokens
        stage.total_tokens += prompt_tokens + completion_tokens
        stage.duration_sec += duration_sec
        stage.retries_count += retries
        stage.errors_count += errors

        # Calculate cost
        cost_in = (prompt_tokens / 1_000_000) * self.cfg.expensive_input_cost_per_1m
        cost_out = (completion_tokens / 1_000_000) * self.cfg.expensive_output_cost_per_1m
        stage.cost_usd += cost_in + cost_out

    def record_stage_misc(self, stage_key: str, items: int, duration_sec: float):
        """Record non-LLM local compute stages."""
        if stage_key in self.stages:
            stage = self.stages[stage_key]
            stage.items_processed += items
            stage.duration_sec += duration_sec

    def generate_report(
        self,
        papers_processed: int,
        total_chunks: int,
        total_triplets: int,
        flagged_triplets: int,
        verified_triplets: int,
    ) -> CostReport:
        """Compile comprehensive CostReport with savings analysis."""
        total_wall_sec = time.perf_counter() - self.start_time

        total_prompt = sum(s.prompt_tokens for s in self.stages.values())
        total_comp = sum(s.completion_tokens for s in self.stages.values())
        total_tok = total_prompt + total_comp
        total_cost = sum(s.cost_usd for s in self.stages.values())

        # Counterfactual: What if extraction also used the expensive model?
        tier1_prompt = self.stages["extraction_tier1"].prompt_tokens
        tier1_comp = self.stages["extraction_tier1"].completion_tokens
        expensive_extraction_cost = (
            (tier1_prompt / 1_000_000) * self.cfg.expensive_input_cost_per_1m
            + (tier1_comp / 1_000_000) * self.cfg.expensive_output_cost_per_1m
        )
        baseline_all_expensive = expensive_extraction_cost + self.stages["verification_tier2"].cost_usd

        savings_usd = max(0.0, baseline_all_expensive - total_cost)
        reduction_pct = (
            (savings_usd / baseline_all_expensive * 100.0)
            if baseline_all_expensive > 0
            else 0.0
        )

        flagged_ratio = (
            (flagged_triplets / total_triplets * 100.0) if total_triplets > 0 else 0.0
        )
        avg_cost_paper = (
            (total_cost / papers_processed) if papers_processed > 0 else 0.0
        )

        throughput_pps = (
            (papers_processed / total_wall_sec) if total_wall_sec > 0 else 0.0
        )
        throughput_tps = (total_tok / total_wall_sec) if total_wall_sec > 0 else 0.0

        report = CostReport(
            target_corpus_size=self.cfg.target_papers,
            papers_processed=papers_processed,
            total_chunks=total_chunks,
            total_triplets_extracted=total_triplets,
            total_triplets_flagged=flagged_triplets,
            total_triplets_verified=verified_triplets,
            flagged_ratio_pct=round(flagged_ratio, 2),
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_comp,
            total_tokens=total_tok,
            total_cost_usd=round(total_cost, 4),
            baseline_all_expensive_cost_usd=round(baseline_all_expensive, 4),
            cost_savings_usd=round(savings_usd, 4),
            cost_reduction_pct=round(reduction_pct, 1),
            total_wall_clock_sec=round(total_wall_sec, 2),
            throughput_papers_per_sec=round(throughput_pps, 2),
            throughput_tokens_per_sec=round(throughput_tps, 2),
            average_cost_per_paper_usd=round(avg_cost_paper, 5),
            stages=self.stages,
        )

        # Save to JSON
        with open(self.cfg.cost_report_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        # Save to Markdown Summary
        self._write_markdown_summary(report)
        logger.info(
            f"Scale run cost report generated: ${report.total_cost_usd:.4f} "
            f"(Saved ${report.cost_savings_usd:.4f} / {report.cost_reduction_pct:.1f}% via tiered models)."
        )

        return report

    def _write_markdown_summary(self, report: CostReport):
        """Write human-readable markdown cost dashboard summary."""
        md_content = f"""# Phase 10 Scale-Up: Cost & Token Tracking Report

**Timestamp:** {report.timestamp}  
**Corpus Scale:** {report.papers_processed} / {report.target_corpus_size} papers ({report.total_chunks} chunks, {report.total_triplets_extracted} triplets)

---

## 1. Executive Cost & Savings Summary

| Metric | Tiered Pipeline (Actual) | All-Expensive Baseline | Delta / Savings |
| :--- | :--- | :--- | :--- |
| **Total Pipeline Cost** | **${report.total_cost_usd:.4f}** | **${report.baseline_all_expensive_cost_usd:.4f}** | **-${report.cost_savings_usd:.4f} ({report.cost_reduction_pct:.1f}% Savings)** |
| **Average Cost per Paper** | **${report.average_cost_per_paper_usd:.5f}** | **${(report.baseline_all_expensive_cost_usd / max(1, report.papers_processed)):.5f}** | **{(100 - (report.total_cost_usd / max(0.0001, report.baseline_all_expensive_cost_usd) * 100)):.1f}% reduction** |
| **Total Tokens Consumed** | {report.total_tokens:,} | {report.total_tokens:,} | — |
| **Total Wall Clock Time** | {report.total_wall_clock_sec:.2f}s ({report.throughput_papers_per_sec:.2f} papers/s) | — | — |

---

## 2. Model Tiering Efficiency Breakdown

The system implements a **Cheap-Model-First** architecture where the vast majority of raw extraction runs on Tier 1 (`{self.cfg.cheap_model}`), and Tier 2 (`{self.cfg.expensive_model}`) is reserved strictly for the **{report.flagged_ratio_pct}%** of triplets flagged by confidence or contradiction checks.

| Stage | Model Tier | Items Processed | Prompt Tokens | Completion Tokens | Total Cost (USD) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Extraction** | `{self.cfg.cheap_model}` (Tier 1) | {report.stages['extraction_tier1'].items_processed:,} chunks | {report.stages['extraction_tier1'].prompt_tokens:,} | {report.stages['extraction_tier1'].completion_tokens:,} | ${report.stages['extraction_tier1'].cost_usd:.4f} |
| **2. Verification (Flagged)** | `{self.cfg.expensive_model}` (Tier 2) | {report.stages['verification_tier2'].items_processed:,} triplets | {report.stages['verification_tier2'].prompt_tokens:,} | {report.stages['verification_tier2'].completion_tokens:,} | ${report.stages['verification_tier2'].cost_usd:.4f} |
| **3. Entity Resolution** | `all-MiniLM-L6-v2 + Dedup` | {report.stages['entity_resolution'].items_processed:,} entities | — | — | $0.0000 (Local) |
| **4. Vector Indexing** | `all-MiniLM-L6-v2 (384-d)` | {report.stages['graph_indexing'].items_processed:,} chunks | — | — | $0.0000 (Local) |

---

## 3. Scale-Up Feasibility Projection

| Target Corpus Size | Estimated Total Tokens | Tiered Architecture Cost | Naive Single-Model Cost | Projected Savings |
| :--- | :--- | :--- | :--- | :--- |
| **500 Papers** | {report.total_tokens:,} | **${report.total_cost_usd:.2f}** | ${report.baseline_all_expensive_cost_usd:.2f} | **${report.cost_savings_usd:.2f}** |
| **1,000 Papers** | {report.total_tokens * 2:,} | **${(report.total_cost_usd * 2):.2f}** | ${(report.baseline_all_expensive_cost_usd * 2):.2f} | **${(report.cost_savings_usd * 2):.2f}** |
| **5,000 Papers** | {report.total_tokens * 10:,} | **${(report.total_cost_usd * 10):.2f}** | ${(report.baseline_all_expensive_cost_usd * 10):.2f} | **${(report.cost_savings_usd * 10):.2f}** |
"""
        with open(self.cfg.cost_summary_md, "w", encoding="utf-8") as f:
            f.write(md_content)
