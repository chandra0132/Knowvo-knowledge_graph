import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymupdf  # PyMuPDF
from processor.config import ProcessorConfig, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pdf_processor")


class PDFProcessor:
    """Extracts text from PDFs, detects sections, and chunks text per section."""

    # Common section header keywords in scientific literature
    SECTION_KEYWORDS = [
        "ABSTRACT",
        "INTRODUCTION",
        "RELATED WORK",
        "BACKGROUND",
        "LITERATURE REVIEW",
        "METHODOLOGY",
        "METHOD",
        "METHODS",
        "APPROACH",
        "PROPOSED METHOD",
        "SYSTEM MODEL",
        "EXPERIMENTS",
        "EXPERIMENTAL SETUP",
        "EVALUATION",
        "RESULTS",
        "RESULTS AND ANALYSIS",
        "DISCUSSION",
        "LIMITATIONS",
        "CONCLUSION",
        "CONCLUSIONS",
        "REFERENCES",
        "BIBLIOGRAPHY",
        "APPENDIX",
    ]

    # Regex pattern to match section headers (e.g., "1 Introduction", "3. Methodology", "ABSTRACT")
    HEADER_REGEX = re.compile(
        r"^(?:"
        r"(?:\d{1,2}|[I|V|X]+|[A-Z])[\.\s]+"  # Header numbering like 1., 1, I., A.
        r")?"
        r"("
        r"ABSTRACT|INTRODUCTION|RELATED WORK|BACKGROUND|LITERATURE REVIEW|"
        r"METHODOLOGY|METHOD|METHODS|APPROACH|PROPOSED METHOD|SYSTEM MODEL|"
        r"EXPERIMENTS|EXPERIMENTAL SETUP|EVALUATION|RESULTS|RESULTS AND ANALYSIS|"
        r"DISCUSSION|LIMITATIONS|CONCLUSION|CONCLUSIONS|REFERENCES|BIBLIOGRAPHY|APPENDIX"
        r")"
        r"(?:[\:\.\s]+.*)?$",
        re.IGNORECASE,
    )

    FOOTER_HEADER_NOISE = re.compile(
        r"^(?:arXiv:\d+\.\d+v\d+.*|Preprint.*|Under review.*|Page \d+ of \d+|\d+\s*$)",
        re.IGNORECASE,
    )

    def __init__(self, cfg: Optional[ProcessorConfig] = None):
        self.cfg = cfg or config
        self.cfg.ensure_directories()

    def clean_text(self, text: str) -> str:
        """Clean raw text: fix hyphenation, remove line noise, normalize whitespace."""
        # Join hyphenated words split across lines
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
        
        # Split lines, filter header/footer noise
        clean_lines = []
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str:
                clean_lines.append("")
                continue
            if self.FOOTER_HEADER_NOISE.match(line_str):
                continue
            clean_lines.append(line_str)

        joined = "\n".join(clean_lines)
        # Normalize multiple empty lines to double linebreaks
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()

    def _is_section_header(self, text_block: str) -> Tuple[bool, Optional[str]]:
        """Determine if a text block/line represents a section heading."""
        lines = [l.strip() for l in text_block.strip().splitlines() if l.strip()]
        if not lines:
            return False, None

        first_line = lines[0]
        # Section headers are usually short (< 90 chars)
        if len(first_line) > 90:
            return False, None

        match = self.HEADER_REGEX.match(first_line)
        if match:
            # Clean section header label
            header_text = first_line.strip()
            return True, header_text

        # Also check exact uppercase section names
        upper_line = first_line.upper()
        for kw in self.SECTION_KEYWORDS:
            if upper_line == kw or upper_line == f"1 {kw}" or upper_line == f"1. {kw}":
                return True, first_line.strip()

        return False, None

    def extract_sections(self, pdf_path: Path) -> List[Dict[str, str]]:
        """Extract text grouped by sections from a PDF file using PyMuPDF."""
        doc = pymupdf.open(pdf_path)
        sections: List[Dict[str, str]] = []
        
        current_section = "Header/Abstract"
        current_blocks: List[str] = []

        for page in doc:
            blocks = page.get_text("blocks")
            for b in blocks:
                # b[4] is text string
                text = b[4].strip()
                if not text:
                    continue

                is_header, header_name = self._is_section_header(text)
                if is_header and header_name:
                    # Save accumulated content for prior section if any
                    if current_blocks:
                        section_text = self.clean_text("\n\n".join(current_blocks))
                        if section_text:
                            sections.append({
                                "section_name": current_section,
                                "text": section_text,
                            })
                        current_blocks = []

                    current_section = header_name
                    # If block contains text beyond just header line, keep remainder
                    lines = [l for l in text.splitlines() if l.strip()]
                    if len(lines) > 1:
                        remainder = "\n".join(lines[1:])
                        current_blocks.append(remainder)
                else:
                    current_blocks.append(text)

        # Flush last section
        if current_blocks:
            section_text = self.clean_text("\n\n".join(current_blocks))
            if section_text:
                sections.append({
                    "section_name": current_section,
                    "text": section_text,
                })

        doc.close()
        
        # If section detection produced no recognized headers, fallback to 1 section
        if not sections:
            full_text = self.clean_text("\n\n".join(current_blocks))
            sections = [{"section_name": "Full Document", "text": full_text}]

        return sections

    def create_chunks(self, paper_id: str, sections: List[Dict[str, str]]) -> List[Dict]:
        """Chunk sections into section-aware chunks under max character limits."""
        chunks: List[Dict] = []
        global_chunk_idx = 0

        for sec in sections:
            sec_name = sec["section_name"]
            sec_text = sec["text"].strip()
            
            # Skip references/bibliography sections from extraction pipeline if desired
            if any(sec_name.upper().startswith(r) for r in ["REFERENCES", "BIBLIOGRAPHY"]):
                continue

            if not sec_text or len(sec_text) < self.cfg.min_chunk_char_size:
                continue

            # If section text fits in a single chunk
            if len(sec_text) <= self.cfg.max_chunk_char_size:
                chunks.append({
                    "chunk_id": f"{paper_id}_c{global_chunk_idx}",
                    "paper_id": paper_id,
                    "section": sec_name,
                    "chunk_index": global_chunk_idx,
                    "text": sec_text,
                    "char_count": len(sec_text),
                    "token_estimate": len(sec_text) // 4,
                })
                global_chunk_idx += 1
            else:
                # Split long sections by paragraphs (\n\n)
                paragraphs = [p.strip() for p in sec_text.split("\n\n") if p.strip()]
                buffer: List[str] = []
                buffer_len = 0

                for para in paragraphs:
                    if buffer_len + len(para) + 2 > self.cfg.max_chunk_char_size and buffer:
                        chunk_text = "\n\n".join(buffer)
                        chunks.append({
                            "chunk_id": f"{paper_id}_c{global_chunk_idx}",
                            "paper_id": paper_id,
                            "section": sec_name,
                            "chunk_index": global_chunk_idx,
                            "text": chunk_text,
                            "char_count": len(chunk_text),
                            "token_estimate": len(chunk_text) // 4,
                        })
                        global_chunk_idx += 1
                        buffer = [para]
                        buffer_len = len(para)
                    else:
                        buffer.append(para)
                        buffer_len += len(para) + 2

                if buffer:
                    chunk_text = "\n\n".join(buffer)
                    if len(chunk_text) >= self.cfg.min_chunk_char_size:
                        chunks.append({
                            "chunk_id": f"{paper_id}_c{global_chunk_idx}",
                            "paper_id": paper_id,
                            "section": sec_name,
                            "chunk_index": global_chunk_idx,
                            "text": chunk_text,
                            "char_count": len(chunk_text),
                            "token_estimate": len(chunk_text) // 4,
                        })
                        global_chunk_idx += 1

        return chunks

    def process_paper(self, pdf_path: Path, paper_id: str) -> Dict:
        """Process a single PDF paper into section structures and chunks."""
        logger.info(f"Processing paper '{paper_id}' from {pdf_path.name}...")
        sections = self.extract_sections(pdf_path)
        chunks = self.create_chunks(paper_id, sections)

        processed_data = {
            "paper_id": paper_id,
            "pdf_path": str(pdf_path),
            "total_sections": len(sections),
            "total_chunks": len(chunks),
            "sections": sections,
            "chunks": chunks,
        }

        output_file = self.cfg.processed_dir / f"{paper_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Processed '{paper_id}': {len(sections)} sections, {len(chunks)} chunks saved to {output_file.name}"
        )
        return processed_data

    def process_all_cached_papers(self) -> List[Dict]:
        """Process all PDFs in raw_pdfs_dir into /data/processed/{paper_id}.json."""
        manifest_path = self.cfg.manifest_file
        pdf_files: List[Tuple[Path, str]] = []

        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    pid = rec["paper_id"]
                    pdf_p = self.cfg.base_dir / rec["local_path"]
                    if pdf_p.exists():
                        pdf_files.append((pdf_p, pid))

        if not pdf_files:
            # Fallback to direct directory scan
            for p in self.cfg.raw_pdfs_dir.glob("*.pdf"):
                pdf_files.append((p, p.stem))

        logger.info(f"Processing {len(pdf_files)} PDF papers...")
        results = []
        for pdf_path, pid in pdf_files:
            try:
                res = self.process_paper(pdf_path, pid)
                results.append(res)
            except Exception as e:
                logger.error(f"Failed to process paper {pid}: {e}")

        logger.info(f"Completed processing {len(results)} papers into {self.cfg.processed_dir}")
        return results


def main():
    processor = PDFProcessor()
    processed = processor.process_all_cached_papers()
    print(f"\nDocument Processing complete! Processed {len(processed)} papers into /data/processed/")


if __name__ == "__main__":
    main()
