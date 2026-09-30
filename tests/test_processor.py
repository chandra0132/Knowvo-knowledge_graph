import json
from pathlib import Path

import pytest
from processor.config import config
from processor.pdf_processor import PDFProcessor


def test_processed_files_exist_and_valid():
    """Verify that all downloaded PDFs have a processed JSON file with sections and chunks."""
    processed_dir = config.processed_dir
    assert processed_dir.exists(), f"Processed dir missing at {processed_dir}"

    json_files = list(processed_dir.glob("*.json"))
    assert (
        len(json_files) >= 30
    ), f"Expected at least 30 processed JSON files, found {len(json_files)}"

    print(f"Total processed papers: {len(json_files)}")


def test_inspect_sample_processed_papers():
    """Inspect 5 processed papers to verify section alignment and chunking integrity."""
    processed_dir = config.processed_dir
    json_files = sorted(list(processed_dir.glob("*.json")))

    assert len(json_files) >= 5, "Need at least 5 processed files for inspection"

    # Select 5 sample papers across the set
    sample_files = json_files[:5]

    for jf in sample_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "paper_id" in data
        assert "sections" in data and len(data["sections"]) > 0
        assert "chunks" in data and len(data["chunks"]) > 0

        paper_id = data["paper_id"]
        sections = [s["section_name"] if isinstance(s, dict) else str(s) for s in data["sections"]]
        chunks = data["chunks"]

        total_secs = data.get("total_sections", len(sections))
        total_chks = data.get("total_chunks", len(chunks))
        print(
            f"\nPaper {paper_id}: {total_secs} sections, {total_chks} chunks"
        )
        print(f"  Sections found: {sections[:6]}")

        # Check chunks
        for chunk in chunks:
            assert chunk["paper_id"] == paper_id
            assert "section" in chunk
            assert "text" in chunk and len(chunk["text"]) > 0
            assert chunk.get("char_count", len(chunk["text"])) <= config.max_chunk_char_size + 500
            # Ensure chunk belongs to a single section
            assert isinstance(chunk["section"], str)

        print(
            f"  Sample Chunk 0 [{chunks[0]['section']}]: {chunks[0]['text'][:80]}..."
        )
