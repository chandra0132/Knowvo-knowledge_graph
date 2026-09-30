import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from extractor.llm_extractor import KnowledgeExtractor
from extractor.schema import ExtractedTriplet
from graph.neo4j_client import Neo4jGraphClient
from graphrag.vector_index import ChunkVectorIndexer
from scale.config import ScaleConfig, config
from scale.cost_tracker import CostReport, CostTracker
from verification.feedback import FeedbackLoop
from verification.flagging import TripletFlaggingEngine
from verification.graph_updater import GraphVerificationUpdater
from verification.verifier import TripletVerifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("async_pipeline")


class AsyncScalePipeline:
    """High-throughput async batch pipeline with tiered model execution and token tracking."""

    def __init__(self, cfg: Optional[ScaleConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()
        self.cost_tracker = CostTracker(self.cfg)
        self.extractor = KnowledgeExtractor()
        self.flagger = TripletFlaggingEngine()
        self.verifier = TripletVerifier()
        self.feedback_mgr = FeedbackLoop()
        self.graph_updater = GraphVerificationUpdater()

    def _load_checkpoint(self) -> Set[str]:
        """Load set of already-processed paper IDs from checkpoint file."""
        if self.cfg.checkpoint_file.exists():
            try:
                with open(self.cfg.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    processed = set(data.get("processed_paper_ids", []))
                    logger.info(f"Loaded checkpoint with {len(processed)} previously processed papers.")
                    return processed
            except Exception as e:
                logger.warning(f"Error loading checkpoint: {e}")
        return set()

    def _save_checkpoint(self, processed_paper_ids: Set[str]):
        """Persist checkpoint state to disk atomically."""
        temp_file = self.cfg.checkpoint_file.with_suffix(".tmp")
        data = {
            "processed_paper_ids": list(processed_paper_ids),
            "last_updated": time.time(),
            "count": len(processed_paper_ids),
        }
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self.cfg.checkpoint_file)

    async def _process_chunk_with_retry(
        self,
        chunk: Dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> Tuple[List[ExtractedTriplet], int, int, int]:
        """Process an individual chunk with semaphore concurrency and exponential backoff on errors."""
        async with semaphore:
            retries = 0
            delay = self.cfg.initial_retry_delay_sec

            for attempt in range(self.cfg.max_retries + 1):
                t0 = time.perf_counter()
                try:
                    # Run extraction in worker thread
                    triplets = await asyncio.to_thread(self.extractor.extract_chunk, chunk)
                    elapsed = time.perf_counter() - t0

                    # Calculate / estimate token counts
                    text_len = len(chunk.get("text", ""))
                    prompt_tok = max(150, int(text_len / 3.8) + 450)  # prompt template + text
                    comp_tok = max(40, len(triplets) * 65)

                    return triplets, prompt_tok, comp_tok, retries

                except Exception as e:
                    retries += 1
                    if attempt == self.cfg.max_retries:
                        logger.error(f"Chunk {chunk.get('chunk_id')} failed after {self.cfg.max_retries} retries: {e}")
                        # Fallback to rule-based extraction
                        fallback_triplets = self.extractor._rule_based_fallback_extract(chunk)
                        return fallback_triplets, 200, 30, retries

                    # Exponential backoff with random jitter
                    jitter = random.uniform(0.05, 0.25)
                    sleep_time = min(self.cfg.max_retry_delay_sec, delay * (self.cfg.backoff_factor ** attempt) + jitter)
                    logger.warning(f"Retry {attempt+1}/{self.cfg.max_retries} for chunk {chunk.get('chunk_id')} in {sleep_time:.2f}s: {e}")
                    await asyncio.sleep(sleep_time)

        return [], 0, 0, 0

    async def _process_paper_async(
        self,
        paper_file: Path,
        semaphore: asyncio.Semaphore,
    ) -> Tuple[str, List[Dict[str, Any]], int, int, int]:
        """Process all chunks of a single paper concurrently."""
        try:
            with open(paper_file, "r", encoding="utf-8") as f:
                paper_data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading paper {paper_file.name}: {e}")
            return paper_file.stem, [], 0, 0, 1

        paper_id = paper_data.get("paper_id", paper_file.stem)
        chunks = paper_data.get("chunks", [])
        if not chunks:
            return paper_id, [], 0, 0, 0

        # Process chunks concurrently within semaphore limit
        tasks = [self._process_chunk_with_retry(c, semaphore) for c in chunks]
        results = await asyncio.gather(*tasks)

        all_paper_triplets: List[Dict[str, Any]] = []
        tot_prompt = 0
        tot_comp = 0
        tot_retries = 0

        for triplets, p_tok, c_tok, rets in results:
            tot_prompt += p_tok
            tot_comp += c_tok
            tot_retries += rets
            for t in triplets:
                all_paper_triplets.append(t.model_dump())

        # Save individual extraction file
        out_file = self.cfg.extractions_dir / f"{paper_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "paper_id": paper_id,
                    "extracted_count": len(all_paper_triplets),
                    "triplets": all_paper_triplets,
                },
                f,
                indent=2,
            )

        return paper_id, all_paper_triplets, tot_prompt, tot_comp, tot_retries

    async def run_batch_extraction(
        self,
        paper_files: List[Path],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Run async batch extraction (Tier 1 Cheap Model) across paper files."""
        semaphore = asyncio.Semaphore(self.cfg.max_concurrency)
        processed_set = self._load_checkpoint()
        
        pending_files = [p for p in paper_files if p.stem not in processed_set]
        logger.info(f"Starting async batch extraction on {len(pending_files)} papers (concurrency={self.cfg.max_concurrency}).")

        all_triplets: List[Dict[str, Any]] = []
        total_chunks = 0
        
        # Process in batches to control memory and checkpoint frequently
        for i in range(0, len(pending_files), self.cfg.batch_size):
            batch = pending_files[i : i + self.cfg.batch_size]
            t_batch_start = time.perf_counter()

            tasks = [self._process_paper_async(pf, semaphore) for pf in batch]
            batch_results = await asyncio.gather(*tasks)

            batch_prompt_tok = 0
            batch_comp_tok = 0
            batch_retries = 0
            batch_triplet_count = 0

            for pid, triplets, p_tok, c_tok, rets in batch_results:
                processed_set.add(pid)
                all_triplets.extend(triplets)
                batch_prompt_tok += p_tok
                batch_comp_tok += c_tok
                batch_retries += rets
                batch_triplet_count += len(triplets)

            batch_dur = time.perf_counter() - t_batch_start
            
            # Record metrics in cost tracker
            self.cost_tracker.record_extraction(
                prompt_tokens=batch_prompt_tok,
                completion_tokens=batch_comp_tok,
                duration_sec=batch_dur,
                retries=batch_retries,
                chunks_count=sum(1 for _ in batch_results),
            )

            # Checkpoint
            self._save_checkpoint(processed_set)
            logger.info(
                f"Batch {i//self.cfg.batch_size + 1}/{(len(pending_files)-1)//self.cfg.batch_size + 1} complete: "
                f"{len(batch)} papers, {batch_triplet_count} triplets ({batch_dur:.2f}s)."
            )

        # If resumed from checkpoint, account for already extracted papers' tokens in cost tracker
        if len(pending_files) < len(paper_files):
            cached_count = len(paper_files) - len(pending_files)
            # Aggregate token metrics for checkpointed papers
            cached_prompt_tok = 0
            cached_comp_tok = 0
            cached_chunks = 0
            for pf in paper_files:
                if pf.stem in processed_set and pf not in pending_files:
                    try:
                        with open(pf, "r", encoding="utf-8") as f:
                            pd = json.load(f)
                            chunks = pd.get("chunks", [])
                            cached_chunks += len(chunks)
                            for c in chunks:
                                cached_prompt_tok += max(150, int(len(c.get("text", "")) / 3.8) + 450)
                    except Exception:
                        pass
                    ext_file = self.cfg.extractions_dir / f"{pf.stem}.json"
                    if ext_file.exists():
                        try:
                            with open(ext_file, "r", encoding="utf-8") as f:
                                ed = json.load(f)
                                cached_comp_tok += max(40, len(ed.get("triplets", [])) * 65)
                        except Exception:
                            pass
            if cached_prompt_tok > 0 or cached_comp_tok > 0:
                self.cost_tracker.record_extraction(
                    prompt_tokens=cached_prompt_tok,
                    completion_tokens=cached_comp_tok,
                    duration_sec=0.0,
                    retries=0,
                    chunks_count=cached_chunks,
                )

        # Also load already existing triplets if resumed
        if self.cfg.all_triplets_file.exists() and len(pending_files) < len(paper_files):
            existing_triplets = []
            try:
                with open(self.cfg.all_triplets_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            existing_triplets.append(json.loads(line))
                # Merge deduplicated
                seen = { (t.get("subject"), t.get("relation"), t.get("object"), t.get("paper_id")) for t in all_triplets }
                for et in existing_triplets:
                    key = (et.get("subject"), et.get("relation"), et.get("object"), et.get("paper_id"))
                    if key not in seen:
                        all_triplets.append(et)
            except Exception as e:
                logger.warning(f"Error reading existing triplets file: {e}")

        # Persist all_triplets.jsonl
        with open(self.cfg.all_triplets_file, "w", encoding="utf-8") as f:
            for t in all_triplets:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

        return all_triplets, len(processed_set)

    def run_tiered_verification(
        self,
        all_triplets: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Flag low-confidence items and run Tier 2 Expensive Verification ONLY on flagged subset."""
        logger.info(f"Starting Tier 2 verification pass on {len(all_triplets)} triplets...")
        t0 = time.perf_counter()

        # Step 1: Flagging (low confidence < 0.70 or contradiction)
        flagged_items = self.flagger.flag_triplets(
            triplets=all_triplets,
            save_to_file=True,
        )
        logger.info(
            f"Flagged {len(flagged_items)} / {len(all_triplets)} triplets "
            f"({(len(flagged_items)/max(1, len(all_triplets))*100):.1f}% flagged for Tier 2 verification)."
        )

        # Save flagged triplets
        with open(self.cfg.flagged_triplets_file, "w", encoding="utf-8") as f:
            for item in flagged_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # Step 2: Verification with expensive model only on flagged items
        verification_results: List[Dict[str, Any]] = []
        verified_prompt_tok = 0
        verified_comp_tok = 0

        for item in flagged_items:
            outcome = self.verifier.verify_triplet(item)
            verification_results.append(outcome)

            # Estimate / track Tier 2 token usage
            prompt_tok = 420 + len(item.get("triplet", {}).get("evidence_span", "")) // 3
            comp_tok = 120
            verified_prompt_tok += prompt_tok
            verified_comp_tok += comp_tok

        dur = time.perf_counter() - t0
        self.cost_tracker.record_verification(
            prompt_tokens=verified_prompt_tok,
            completion_tokens=verified_comp_tok,
            duration_sec=dur,
            triplets_count=len(flagged_items),
        )

        # Save verification results
        with open(self.cfg.verification_results_file, "w", encoding="utf-8") as f:
            for res in verification_results:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")

        # Step 3: Self-improvement feedback loop
        examples = self.feedback_mgr.extract_feedback_examples(verification_results)
        if examples:
            self.feedback_mgr.persist_dynamic_examples(examples)

        return flagged_items, verification_results

    def run_graph_and_vector_load(self, all_triplets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest triplets into Neo4j graph and update native vector index."""
        logger.info("Ingesting triplets into Neo4j graph...")
        t0 = time.perf_counter()
        
        with Neo4jGraphClient() as client:
            client.ingest_triplets_batch(all_triplets)
            stats = client.get_graph_stats()

        dur = time.perf_counter() - t0
        self.cost_tracker.record_stage_misc("entity_resolution", stats.get("entity_nodes", 0), dur * 0.4)
        self.cost_tracker.record_stage_misc("graph_indexing", stats.get("total_relationships", 0), dur * 0.6)

        # Update Vector Index
        try:
            indexer = ChunkVectorIndexer()
            indexer.index_all_chunks()
            indexer.close()
        except Exception as e:
            logger.warning(f"Vector indexing update notice: {e}")

        return stats

    async def execute_scale_run(self, target_count: Optional[int] = None) -> CostReport:
        """Execute full 500-paper scale up pipeline and generate cost report."""
        target = target_count or self.cfg.target_papers
        logger.info(f"=== INITIATING PHASE 10 SCALE-UP RUN (Target: {target} Papers) ===")

        # 1. Discover or build corpus papers
        paper_files = sorted(list(self.cfg.processed_dir.glob("*.json")))
        if len(paper_files) < target:
            logger.info(f"Found {len(paper_files)} papers in {self.cfg.processed_dir}. Scaling up corpus to {target} papers...")
            from scale.corpus_scaler import CorpusScaler
            scaler = CorpusScaler()
            scaler.ensure_scaled_corpus(target_count=target)
            paper_files = sorted(list(self.cfg.processed_dir.glob("*.json")))

        paper_files = paper_files[:target]
        logger.info(f"Targeting {len(paper_files)} papers for full pipeline execution.")

        # 2. Tier 1 Async Batch Extraction
        all_triplets, processed_papers_count = await self.run_batch_extraction(paper_files)

        # Count total chunks
        total_chunks = 0
        for pf in paper_files:
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    total_chunks += len(d.get("chunks", []))
            except Exception:
                pass

        # 3. Tier 2 Expensive Verification on Flagged Items Only
        flagged_items, verification_results = self.run_tiered_verification(all_triplets)

        # 4. Neo4j Graph & Vector Indexing
        graph_stats = self.run_graph_and_vector_load(all_triplets)

        # 5. Compile Cost Report
        report = self.cost_tracker.generate_report(
            papers_processed=processed_papers_count,
            total_chunks=total_chunks,
            total_triplets=len(all_triplets),
            flagged_triplets=len(flagged_items),
            verified_triplets=len(verification_results),
        )

        logger.info(f"=== SCALE RUN COMPLETE ===")
        logger.info(f"Papers Processed: {report.papers_processed}")
        logger.info(f"Total Triplets Extracted: {report.total_triplets_extracted}")
        logger.info(f"Total Pipeline Cost: ${report.total_cost_usd:.4f} (Saved ${report.cost_savings_usd:.4f})")
        logger.info(f"Neo4j Entities: {graph_stats.get('entity_nodes', 0)}, Relationships: {graph_stats.get('total_relationships', 0)}")

        return report
