# Self-Improving Knowledge Graph

A Self-Improving Knowledge Graph system for scientific literature using LLMs, GraphRAG, and Neo4j.

## Project Structure

```
/collector      # arxiv fetch + cache
/processor      # pdf -> clean text -> chunks
/extractor      # LLM extraction, schema, prompts
/graph          # neo4j client, cypher, schema/constraints
/graphrag        # query analyzer, retrieval, evidence fusion
/verification    # confidence scoring, feedback loop
/eval            # benchmark + metrics
/api            # FastAPI
/frontend       # React
/data           # raw_pdfs/, cache/, benchmark/
```

## Quick Start

1. Start Neo4j via Docker Compose:
   ```bash
   docker compose up -d
   ```
   Neo4j Browser will be available at `http://localhost:7474`.

2. Install dependencies:
   ```bash
   python3 -m uv venv .venv
   source .venv/bin/activate
   python3 -m uv pip install -e .
   ```

3. Run tests:
   ```bash
   python -m pytest
   ```
