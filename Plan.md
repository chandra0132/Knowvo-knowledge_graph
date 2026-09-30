# Self-Improving Knowledge Graph — Execution Plan for Agentic (Vibe-Coding) Build

*Companion to: Self_Improving_Knowledge_Graph_Project.docx*
*Target tool: Antigravity (or Cursor / Windsurf / Claude Code) — one phase = one agent session*

---

## 0. How to use this document

Each phase below is written as a **self-contained brief** you can paste into your vibe-coding
platform as a task. Every phase has:

- **Goal** — what "done" means
- **Build this** — concrete scope
- **Give the agent** — context/files it needs
- **Acceptance criteria** — how you verify the agent actually finished, not just "looked busy"

Do not skip acceptance criteria — agentic coding tools drift silently on multi-step pipelines
(they'll extract garbage triplets confidently). Verify each phase manually before moving on.

---

## 1. Updated Technology Decisions (read before you start)

| Layer | Original doc | Recommended for 2026 build | Why |
|---|---|---|---|
| Extraction | spaCy NER + separate LLM pass | LLM structured/tool-calling output as primary extractor; spaCy only for cheap section/sentence triage | One well-schema'd LLM call now outperforms a two-stage pipeline for entity+relation extraction |
| GraphRAG engine | Build from scratch | Start on `neo4j-graphrag-python` (official), fall back to custom Cypher generation only where it's insufficient | Don't rebuild what's maintained upstream |
| Vector store | FAISS/Chroma alongside Neo4j | Neo4j native vector index first; add a separate store only if you want to A/B backends | One fewer moving part, one fewer sync problem |
| Model tiering | Single "an LLM" | Cheap/fast model for bulk extraction → stronger model to verify low-confidence or contradictory triplets | Cost control at 500–5,000 paper scale |
| Observability | None specified | Add Langfuse (or similar) tracing from Phase 3 onward | You cannot debug a silent bad-extraction problem without traces |
| Ontology | Fixed relationship vocabulary | Fixed *core* vocabulary + an LLM-proposed "candidate relation type" queue that a human approves before it's promoted | Prevents graph explosion while still allowing growth |
| Entity resolution | Named as a risk, no method | Embedding similarity blocking + LLM adjudication + canonical ID table (explicit, see Phase 5) | "Normalization" isn't a plan until it's an algorithm |
| Collection | ArXiv API, no compliance detail | Respect ArXiv rate limits (3-second delay, use official `arxiv` Python package), cache all downloaded PDFs locally, never re-fetch | ToS compliance + cost |

---

## 2. Phase Plan

### Phase 0 — Environment & Repo Scaffold
**Goal:** A running repo skeleton with Neo4j reachable and secrets configured.

**Build this:**
- Python project (`uv` or `poetry`), `.env.example` with `ARXIV_*`, `NEO4J_URI/USER/PASSWORD`, `LLM_API_KEY`
- Neo4j via Docker Compose (local first, per original doc's deployment stance)
- Folder structure:
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
**Give the agent:** this table, the folder tree above.

**Acceptance criteria:** `docker compose up` gives a reachable Neo4j browser at :7474; `python -m pytest` runs (even with zero tests) with no import errors.

---

### Phase 1 — Research Collector (V0 scope: 10–50 papers)
**Goal:** Pull a small, cached corpus for one focused domain.

**Build this:**
- Domain choice locked in config (recommend **LLM Hallucination Research** per original doc's rationale — clear entities, competing claims, active field)
- ArXiv fetch via official `arxiv` package, rate-limited, metadata + PDF saved to `/data/raw_pdfs/`, idempotent (skip if already cached)
- A manifest file (`corpus.jsonl`) tracking paper_id, title, authors, date, local path

**Acceptance criteria:** Running the collector twice does not re-download anything; manifest has 30–50 entries; spot check 3 PDFs open correctly.

---

### Phase 2 — Document Processor
**Goal:** Clean, chunked text per paper, section-aware.

**Build this:**
- PDF → text via PyMuPDF, with section detection (Abstract/Intro/Method/Results/etc.) where headers are extractable
- Chunking strategy: chunk by section, not fixed token windows, with paper_id + section stored per chunk
- Store output as `/data/processed/{paper_id}.json`

**Acceptance criteria:** Manually inspect 5 processed papers — sections roughly align with the actual PDF, no chunk spans multiple unrelated sections.

---

### Phase 3 — Knowledge Extractor (the core of the project)
**Goal:** Structured triplets with confidence + evidence, per chunk.

**Build this:**
- Define the extraction schema explicitly (JSON schema or Pydantic model): `subject, subject_type, relation, object, object_type, confidence (0-1), evidence_span, paper_id, section`
- Fixed core relation vocabulary from the original doc (PROPOSES, USES, BUILDS_ON, IMPROVES, CONTRADICTS, EVALUATES, AUTHORED_BY, CITES, EXTENDS, COMPARED_WITH) **plus** a `candidate_relation` field the model can populate if none of the fixed types fit
- One structured-output LLM call per chunk (cheap/fast model), self-reported confidence
- Add Langfuse tracing here — you'll need it
- Log every candidate_relation to `/data/candidate_relations.jsonl` for human review (do not auto-promote into the graph)

**Give the agent:** the schema table above, 2–3 worked examples from the original doc (surface code triplets, BERT triplets).

**Acceptance criteria:** Run on 20 papers; manually verify precision on a random sample of 30 triplets (target >70% correct at this stage — this is expected to be rough pre-verification); confirm every triplet carries evidence_span and paper_id.

---

### Phase 4 — Neo4j Graph Layer
**Goal:** Extracted triplets loaded as a real graph with constraints.

**Build this:**
- Schema constraints: uniqueness on canonical entity ID, indexes on entity name/type
- Load pipeline: triplets → nodes/edges, with paper-level evidence stored as edge properties (not separate nodes, to avoid graph explosion)
- A handful of hand-written Cypher queries matching the original doc's examples (`MATCH (method)-[:IMPROVES]->(problem)...`)

**Acceptance criteria:** Neo4j Browser query returns expected results for 3 manually-verified questions; node count is sane (no obvious duplicate explosion) before entity resolution is even applied.

---

### Phase 5 — Entity Resolution (the gap in the original doc)
**Goal:** Explicit dedup algorithm, not just a stated intention.

**Build this:**
- Embed entity names (Sentence Transformers), block candidates by cosine similarity threshold
- For each candidate pair, LLM adjudication call: same entity? → merge under canonical ID, keep aliases list
- Canonical ID table persisted so re-runs are consistent across corpus growth

**Acceptance criteria:** Before/after entity count on a 50-paper run; spot-check 10 merges manually — no false merges of genuinely distinct entities.

---

### Phase 6 — GraphRAG Engine
**Goal:** Natural-language question → graph traversal → evidence.

**Build this:**
- Start with `neo4j-graphrag-python` for query analysis + Cypher generation/selection
- Native Neo4j vector index for the hybrid path (skip separate vector DB unless you want an A/B)
- Evidence fusion step combining graph paths + vector hits before handing to the answer LLM

**Acceptance criteria:** The 5 example questions from the original doc (Section 16) each return a sensible answer with cited papers and a visible reasoning path.

---

### Phase 7 — Verification & Self-Improvement Loop
**Goal:** Low-confidence/contradictory triplets get flagged and re-checked.

**Build this:**
- Threshold-based flagging of low-confidence triplets
- Contradiction detection: same subject+relation, incompatible objects across papers
- Secondary verification pass using a stronger model against the original evidence span
- Store verification outcome (confirmed/corrected/rejected) and feed corrections back into extraction prompt examples (few-shot refinement, not fine-tuning, at this scale)

**Acceptance criteria:** Run on a batch of flagged triplets — verification changes at least some outcomes (proves the loop isn't a no-op); corrected examples visibly appear in the next extraction run's prompt.

---

### Phase 8 — Evaluation Layer
**Goal:** Numbers, not vibes, on system quality.

**Build this:**
- Hand-build a small benchmark set (20–30 question/answer/expected-evidence triples) — do this *before* scaling the corpus
- Metrics: extraction P/R/F1 against a manually labeled subset, entity-linking accuracy, answer faithfulness (consider RAGAS), citation correctness, latency

**Acceptance criteria:** Benchmark run produces a report file with all metrics populated (not placeholders).

---

### Phase 9 — API + Frontend
**Goal:** The "final user experience" from the original doc, working end to end.

**Build this:**
- FastAPI endpoints: ask question, get answer + evidence + graph path
- React frontend: question box, answer panel, evidence/citation list, interactive graph view (start with Neo4j's own viz or a simple force-directed graph component — don't over-invest here early)

**Acceptance criteria:** A question typed in the UI returns an answer with visible sources within a few seconds on the V1-scale corpus.

---

### Phase 10 — Scale Up (500 → 5,000 papers)
**Goal:** Same pipeline, larger corpus, cost under control.

**Build this:**
- Batch/async processing with retry + backoff
- Cheap-model-first extraction, expensive-model verification only on flagged items (from Phase 7)
- Cost + token tracking dashboard (simple log aggregation is enough)

**Acceptance criteria:** Full 500-paper run completes with a cost report; spot-check quality hasn't degraded vs. the 50-paper baseline.

---

## 3. Suggested order of operations for Antigravity sessions

1. Phases 0–2 in one session (scaffolding + collection + processing) — low risk, verify quickly
2. Phase 3 alone, in its own session — this is the highest-risk phase, give it your full review attention
3. Phases 4–5 together (graph load + entity resolution)
4. Phase 6 alone (GraphRAG) — verify against the 5 sample questions before moving on
5. Phase 7 alone (verification loop)
6. Phase 8 before Phase 9 — build the benchmark *before* the UI so you're not tempted to eyeball quality through a nice frontend
7. Phase 9
8. Phase 10 only after 0–9 are all verified on the small corpus

## 4. What NOT to let the agent decide silently
- Relation vocabulary changes (must go through the candidate_relation review queue, Phase 3)
- Entity merge decisions above a low-confidence threshold (spot check Phase 5 output every run)
- Any auto-promotion of unverified triplets directly into answers (Phase 7 exists specifically to prevent this)
