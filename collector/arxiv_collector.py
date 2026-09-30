import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import arxiv
import certifi
import httpx
from collector.config import CollectorConfig, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("arxiv_collector")


class ArXivCollector:
    """Idempotent ArXiv paper collector for scientific literature."""

    USER_AGENT = "KnowledgeGraphCorpusBuilder/1.0 (Research Literature Collector; mailto:research@example.com)"

    def __init__(self, cfg: Optional[CollectorConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()
        self.manifest_path = self.cfg.manifest_file

    def clean_paper_id(self, paper_id: str) -> str:
        """Sanitize paper ID for filename usage (replace / with _ if legacy format)."""
        return paper_id.replace("/", "_")

    def load_manifest(self) -> Dict[str, dict]:
        """Load existing corpus manifest into a dictionary keyed by paper_id."""
        manifest = {}
        if not self.manifest_path.exists():
            return manifest

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    pid = record.get("paper_id")
                    if pid:
                        manifest[pid] = record
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse line in manifest: {e}")
        return manifest

    def _save_manifest(self, manifest: Dict[str, dict]) -> None:
        """Atomically overwrite manifest file with current records."""
        temp_path = self.manifest_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            for record in manifest.values():
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        temp_path.replace(self.manifest_path)

    def _download_pdf(self, pdf_url: str, output_path: Path) -> bool:
        """Download PDF from URL with HTTPX and certificate verification."""
        # Ensure pdf_url points to .pdf if missing extension
        url = pdf_url if pdf_url.endswith(".pdf") else f"{pdf_url}.pdf"
        headers = {"User-Agent": self.USER_AGENT}
        
        try:
            with httpx.Client(
                verify=certifi.where(),
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                
                # Check response content type or magic bytes for PDF (%PDF)
                if not response.content.startswith(b"%PDF"):
                    # Fallback try original pdf_url without .pdf suffix
                    response = client.get(pdf_url, headers=headers)
                    response.raise_for_status()

                output_path.write_bytes(response.content)
                return True
        except Exception as e:
            logger.error(f"HTTPX download failed for {url}: {e}")
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            return False

    def fetch_corpus(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        rate_limit_delay: Optional[float] = None,
    ) -> List[dict]:
        """
        Fetch papers from ArXiv according to domain query and cache locally.
        
        Args:
            query: ArXiv search query string (defaults to config)
            max_results: Max papers to fetch (defaults to config)
            rate_limit_delay: Delay in seconds between downloads
            
        Returns:
            List of paper metadata records in corpus manifest.
        """
        search_query = query or self.cfg.arxiv_search_query
        target_results = max_results or self.cfg.arxiv_max_results
        delay = (
            rate_limit_delay
            if rate_limit_delay is not None
            else self.cfg.arxiv_rate_limit_delay
        )

        logger.info(
            f"Starting ArXiv fetch: query='{search_query}', max_results={target_results}"
        )

        manifest = self.load_manifest()
        logger.info(f"Loaded existing manifest with {len(manifest)} cached entries.")

        client = arxiv.Client(page_size=min(100, target_results), delay_seconds=delay)
        search = arxiv.Search(
            query=search_query,
            max_results=target_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        downloaded_count = 0
        skipped_count = 0

        for result in client.results(search):
            raw_id = result.get_short_id()
            paper_id = self.clean_paper_id(raw_id)

            pdf_filename = f"{paper_id}.pdf"
            pdf_path = self.cfg.raw_pdfs_dir / pdf_filename
            rel_path = f"data/raw_pdfs/{pdf_filename}"

            # Check if paper is already cached on disk and in manifest
            if pdf_path.exists() and pdf_path.stat().st_size > 0 and paper_id in manifest:
                logger.info(f"Paper '{paper_id}' already cached locally. Skipping.")
                skipped_count += 1
                continue

            logger.info(f"Downloading paper '{paper_id}': {result.title[:60]}...")
            
            success = self._download_pdf(result.pdf_url, pdf_path)
            if success:
                file_size = pdf_path.stat().st_size if pdf_path.exists() else 0

                record = {
                    "paper_id": paper_id,
                    "title": " ".join(result.title.split()),
                    "authors": [author.name for author in result.authors],
                    "published": result.published.isoformat() if result.published else None,
                    "updated": result.updated.isoformat() if result.updated else None,
                    "primary_category": result.primary_category,
                    "categories": result.categories,
                    "summary": " ".join(result.summary.split()),
                    "pdf_url": result.pdf_url,
                    "local_path": rel_path,
                    "file_size_bytes": file_size,
                }

                manifest[paper_id] = record
                self._save_manifest(manifest)
                downloaded_count += 1

                # Respect ArXiv rate limits
                if delay > 0:
                    time.sleep(delay)
            else:
                logger.warning(f"Could not save PDF for '{paper_id}'")

        logger.info(
            f"Fetch completed: {downloaded_count} downloaded, {skipped_count} skipped. Total manifest entries: {len(manifest)}"
        )
        return list(manifest.values())


def main():
    collector = ArXivCollector()
    corpus = collector.fetch_corpus()
    print(f"\nCorpus collection complete! Total papers in manifest: {len(corpus)}")


if __name__ == "__main__":
    main()
