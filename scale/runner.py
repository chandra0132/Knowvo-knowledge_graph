import argparse
import asyncio
import logging
import sys

from scale.async_pipeline import AsyncScalePipeline
from scale.config import config
from scale.quality_checker import QualityChecker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scale_runner")


async def main_async(target_papers: int, run_spotcheck: bool = True):
    """Run full Phase 10 Scale-Up pipeline and spot check validation."""
    logger.info(f"Starting Phase 10 Scaled Corpus Pipeline (Target = {target_papers} papers)...")

    pipeline = AsyncScalePipeline(config)
    cost_report = await pipeline.execute_scale_run(target_count=target_papers)

    print("\n" + "=" * 70)
    print("PHASE 10 SCALE-UP PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Papers Processed:         {cost_report.papers_processed}")
    print(f"Total Chunks:             {cost_report.total_chunks}")
    print(f"Total Triplets:           {cost_report.total_triplets_extracted}")
    print(f"Flagged for Verification: {cost_report.total_triplets_flagged} ({cost_report.flagged_ratio_pct}%)")
    print(f"Total Tokens:             {cost_report.total_tokens:,}")
    print(f"Total Pipeline Cost:      ${cost_report.total_cost_usd:.4f}")
    print(f"Baseline Expensive Cost:  ${cost_report.baseline_all_expensive_cost_usd:.4f}")
    print(f"Cost Savings:             ${cost_report.cost_savings_usd:.4f} ({cost_report.cost_reduction_pct:.1f}% Savings)")
    print(f"Cost Report JSON:         {config.cost_report_file}")
    print(f"Cost Summary Markdown:    {config.cost_summary_md}")
    print("=" * 70 + "\n")

    if run_spotcheck:
        logger.info("Executing Quality Spot-Check against 50-paper baseline...")
        checker = QualityChecker(config)
        quality_metrics = checker.run_full_spotcheck()
        print("\n" + "=" * 70)
        print("PHASE 10 QUALITY SPOT-CHECK REPORT")
        print("=" * 70)
        print(f"Corpus Size:              {quality_metrics.corpus_size_papers} papers")
        print(f"Average Confidence:       {quality_metrics.avg_confidence_score}")
        print(f"Entity Nodes:             {quality_metrics.entity_node_count}")
        print(f"Relationships:            {quality_metrics.relationship_count}")
        print(f"All 5 QA Checks Passed:   {quality_metrics.all_benchmark_queries_passed}")
        print(f"Degraded vs Baseline:     {quality_metrics.quality_degraded_vs_baseline}")
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Phase 10: Scaled Corpus Execution Engine (500 -> 5,000 papers)")
    parser.add_argument(
        "--target",
        type=int,
        default=config.target_papers,
        help="Target number of papers to scale up and process (default: 500)",
    )
    parser.add_argument(
        "--no-spotcheck",
        action="store_true",
        help="Skip quality spot-check execution",
    )
    args = parser.parse_args()

    asyncio.run(main_async(target_papers=args.target, run_spotcheck=not args.no_spotcheck))


if __name__ == "__main__":
    main()
