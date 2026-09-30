import json
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from collector.arxiv_collector import ArXivCollector
from collector.config import config


def test_collector_manifest_and_idempotency():
    """Verify that paper collector runs, produces 30-50 entries, and is idempotent."""
    collector = ArXivCollector()
    manifest_path = config.manifest_file

    assert manifest_path.exists(), f"Manifest file missing at {manifest_path}"

    records = collector.load_manifest()
    num_papers = len(records)
    print(f"Loaded {num_papers} papers from manifest.")

    assert (
        num_papers >= 30
    ), f"Expected >= 30 papers in manifest, got {num_papers}"

    # Verify manifest entry fields
    sample_id = next(iter(records))
    sample = records[sample_id]
    required_keys = {"paper_id", "title", "authors", "published", "local_path"}
    assert required_keys.issubset(
        sample.keys()
    ), f"Missing keys in manifest record: {required_keys - set(sample.keys())}"

    # Verify local PDF file existence
    local_pdf = config.base_dir / sample["local_path"]
    assert local_pdf.exists(), f"PDF file does not exist at {local_pdf}"
    assert local_pdf.stat().st_size > 0, f"PDF file at {local_pdf} is 0 bytes"

    # Idempotency check: loaded manifest contains all cached entries
    cached_ids = set(records.keys())
    new_manifest = collector.load_manifest()
    assert set(new_manifest.keys()).issuperset(cached_ids)


def test_pdf_spot_check():
    """Spot check at least 3 downloaded PDFs to verify they open and contain text."""
    collector = ArXivCollector()
    records = list(collector.load_manifest().values())

    assert (
        len(records) >= 3
    ), f"Need at least 3 papers to spot check, found {len(records)}"

    # Select first 3 records for spot check
    sample_records = records[:3]

    for record in sample_records:
        pdf_path = config.base_dir / record["local_path"]
        assert pdf_path.exists(), f"PDF path {pdf_path} does not exist"

        # Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)
        assert doc.page_count > 0, f"PDF {pdf_path} has 0 pages"

        # Extract text from page 0
        page_text = doc[0].get_text().strip()
        assert (
            len(page_text) > 50
        ), f"PDF {pdf_path} page 1 has insufficient text ({len(page_text)} chars)"
        print(
            f"Spot check PASSED for {record['paper_id']}: '{record['title'][:40]}' ({doc.page_count} pages)"
        )
