import logging
from typing import Any, Dict, List, Set
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("evidence_fusion")


class FusedEvidence(BaseModel):
    """Structured container for fused graph path and vector chunk evidence."""

    context_text: str = Field(
        ..., description="Formatted textual context bundle for the answer generation LLM."
    )
    cited_papers: List[str] = Field(
        default_factory=list, description="Unique paper IDs cited across graph paths and vector hits."
    )
    reasoning_paths: List[str] = Field(
        default_factory=list, description="Human-readable graph traversal reasoning paths."
    )
    vector_chunk_ids: List[str] = Field(
        default_factory=list, description="List of chunk IDs retrieved via vector similarity."
    )
    graph_triplet_count: int = Field(0, description="Total number of graph paths/triplets included.")
    vector_hit_count: int = Field(0, description="Total number of text vector hits included.")


class EvidenceFusor:
    """Fuses graph path evidence and vector chunk hits into a unified context bundle."""

    def fuse(
        self,
        graph_paths: List[Dict[str, Any]],
        vector_hits: List[Dict[str, Any]],
        max_graph_items: int = 10,
        max_vector_items: int = 5,
    ) -> FusedEvidence:
        """Combine, rank, deduplicate, and format evidence from both graph and vector sources."""
        cited_papers_set: Set[str] = set()
        reasoning_paths: List[str] = []

        # 1. Format Graph Traversal Paths
        graph_lines: List[str] = []
        for i, g in enumerate(graph_paths[:max_graph_items], 1):
            subj = g.get("subject", "Unknown")
            rel = g.get("relation", "RELATED_TO")
            obj = g.get("object", "Unknown")
            paper_id = g.get("paper_id", "Unknown")
            evidence = g.get("evidence_span", "").strip()
            conf = g.get("confidence", 0.0)

            if paper_id and paper_id != "unknown" and paper_id != "Unknown":
                cited_papers_set.add(paper_id)

            path_str = f"[{subj}] -[{rel}]-> [{obj}]"
            reasoning_paths.append(f"{path_str} (Paper: {paper_id}, Confidence: {conf:.2f})")

            line = f"{i}. Path: {path_str}\n   Paper: {paper_id}\n   Confidence: {conf:.2f}"
            if evidence:
                line += f'\n   Evidence Span: "{evidence}"'
            graph_lines.append(line)

        # 2. Format Vector Text Chunks
        vector_lines: List[str] = []
        chunk_ids: List[str] = []
        for j, v in enumerate(vector_hits[:max_vector_items], 1):
            cid = v.get("chunk_id", f"chunk_{j}")
            paper_id = v.get("paper_id", "Unknown")
            section = v.get("section", "Unknown")
            text = v.get("text", "").strip()
            score = v.get("score", 0.0)

            chunk_ids.append(cid)
            if paper_id and paper_id != "unknown" and paper_id != "Unknown":
                cited_papers_set.add(paper_id)

            # Limit individual chunk snippet length in context if long
            snippet = text if len(text) <= 800 else text[:800] + "..."
            line = f"{j}. Paper: {paper_id} | Section: {section} | Similarity: {score:.4f}\n   Content: \"{snippet}\""
            vector_lines.append(line)

        # 3. Assemble Fused Context String for LLM
        graph_section = "\n\n".join(graph_lines) if graph_lines else "No specific graph paths found."
        vector_section = "\n\n".join(vector_lines) if vector_lines else "No specific vector text chunks found."

        context_text = f"""=== KNOWLEDGE GRAPH PATHS & TRIPLETS ({len(graph_lines)} paths) ===
{graph_section}

=== RELEVANT TEXT CHUNKS FROM VECTOR INDEX ({len(vector_lines)} chunks) ===
{vector_section}"""

        sorted_cited_papers = sorted(list(cited_papers_set))

        return FusedEvidence(
            context_text=context_text,
            cited_papers=sorted_cited_papers,
            reasoning_paths=reasoning_paths,
            vector_chunk_ids=chunk_ids,
            graph_triplet_count=len(graph_lines),
            vector_hit_count=len(vector_lines),
        )


def main():
    fusor = EvidenceFusor()
    sample_graph = [
        {
            "subject": "CoAL-RAG",
            "relation": "IMPROVES",
            "object": "Retrieval Accuracy",
            "paper_id": "2608.12345v1",
            "confidence": 0.95,
            "evidence_span": "CoAL-RAG improves retrieval accuracy over standard baselines.",
        }
    ]
    sample_vector = [
        {
            "chunk_id": "chunk_1",
            "paper_id": "2608.12345v1",
            "section": "Abstract",
            "text": "We introduce CoAL-RAG for active retrieval augmented generation.",
            "score": 0.88,
        }
    ]
    res = fusor.fuse(sample_graph, sample_vector)
    print("Fused Context:\n", res.context_text)
    print("Cited Papers:", res.cited_papers)
    print("Reasoning Paths:", res.reasoning_paths)


if __name__ == "__main__":
    main()
