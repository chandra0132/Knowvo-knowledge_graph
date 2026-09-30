import logging
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.models import (
    GraphDataResponse,
    GraphLink,
    GraphNode,
    GraphStatsResponse,
    QueryRequest,
    QueryResponse,
)
from graph.neo4j_client import Neo4jGraphClient
from graphrag.engine import GraphRAGEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api")

# Global engine instance
graphrag_engine: Optional[GraphRAGEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graphrag_engine
    logger.info("Initializing GraphRAGEngine on startup...")
    graphrag_engine = GraphRAGEngine()
    yield
    logger.info("Shutting down GraphRAGEngine...")
    if graphrag_engine:
        graphrag_engine.close()


app = FastAPI(
    title="Self-Improving Knowledge Graph API",
    description="FastAPI Backend for GraphRAG Natural Language QA and Knowledge Graph Exploration",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", summary="Health Check")
def health_check():
    return {
        "status": "healthy",
        "service": "Self-Improving Knowledge Graph API",
        "version": "0.1.0",
    }


@app.get("/api/stats", response_model=GraphStatsResponse, summary="Get Knowledge Graph Stats")
def get_graph_stats():
    try:
        with Neo4jGraphClient() as client:
            stats = client.get_graph_stats()
            return GraphStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to retrieve graph stats: {e}")
        raise HTTPException(status_code=500, detail=f"Neo4j connection error: {str(e)}")


@app.get("/api/graph/explore", response_model=GraphDataResponse, summary="Explore Knowledge Graph Subgraph")
def explore_graph(
    keyword: Optional[str] = Query(None, description="Optional entity name keyword filter"),
    limit: int = Query(50, ge=5, le=200, description="Max relationships to return"),
):
    nodes_map = {}
    links = []

    cypher_filtered = """
    MATCH (s:Entity)-[r]->(o:Entity)
    WHERE type(r) <> 'MENTIONED_IN' AND type(r) <> 'BELONGS_TO'
      AND (
        $keyword IS NULL
        OR toLower(s.name) CONTAINS toLower($keyword)
        OR toLower(o.name) CONTAINS toLower($keyword)
      )
    RETURN s.id AS s_id, s.name AS s_name, s.type AS s_type,
           type(r) AS rel_type, r.paper_id AS paper_id, r.confidence AS confidence,
           o.id AS o_id, o.name AS o_name, o.type AS o_type
    LIMIT $limit
    """

    try:
        with Neo4jGraphClient() as client:
            with client.driver.session(database=client.database) as session:
                res = session.run(cypher_filtered, {"keyword": keyword, "limit": limit})
                for rec in res:
                    s_id = rec["s_id"] or rec["s_name"]
                    o_id = rec["o_id"] or rec["o_name"]

                    if s_id not in nodes_map:
                        nodes_map[s_id] = GraphNode(
                            id=s_id,
                            label=rec["s_name"] or s_id,
                            type=rec["s_type"] or "Entity",
                        )

                    if o_id not in nodes_map:
                        nodes_map[o_id] = GraphNode(
                            id=o_id,
                            label=rec["o_name"] or o_id,
                            type=rec["o_type"] or "Entity",
                        )

                    links.append(
                        GraphLink(
                            source=s_id,
                            target=o_id,
                            relation=rec["rel_type"] or "RELATED_TO",
                            paper_id=rec["paper_id"],
                            confidence=rec["confidence"],
                        )
                    )

        return GraphDataResponse(
            nodes=list(nodes_map.values()),
            links=links,
        )
    except Exception as e:
        logger.error(f"Failed to explore graph: {e}")
        raise HTTPException(status_code=500, detail=f"Graph query error: {str(e)}")


@app.post("/api/query", response_model=QueryResponse, summary="Ask Natural Language Question via GraphRAG")
def ask_question(req: QueryRequest):
    global graphrag_engine
    if not graphrag_engine:
        graphrag_engine = GraphRAGEngine()

    start_time = time.perf_counter()
    try:
        result = graphrag_engine.query(
            question=req.question,
            top_k_vector=req.top_k_vector,
            top_k_graph=req.top_k_graph,
        )
        elapsed = time.perf_counter() - start_time

        return QueryResponse(
            question=req.question,
            answer=result["answer"],
            cited_papers=result.get("cited_papers", []),
            reasoning_path=result.get("reasoning_path", []),
            graph_paths=result.get("graph_paths", []),
            vector_hits=result.get("vector_hits", []),
            latency_sec=round(elapsed, 4),
        )
    except Exception as e:
        logger.error(f"GraphRAG query execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"GraphRAG engine error: {str(e)}")


@app.get("/api/scale/cost-report", summary="Get Phase 10 Cost and Token Report")
def get_cost_report():
    import json
    from scale.config import config as scale_config
    if scale_config.cost_report_file.exists():
        try:
            with open(scale_config.cost_report_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading cost report: {e}")
    return {"status": "no_report_yet", "message": "Run Phase 10 scale pipeline to generate cost report."}


@app.get("/api/scale/quality-report", summary="Get Phase 10 Quality Spot-Check Report")
def get_quality_report():
    import json
    from scale.config import config as scale_config
    report_file = scale_config.data_dir / "quality_spotcheck_report.json"
    if report_file.exists():
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading quality report: {e}")
    return {"status": "no_report_yet", "message": "Run Phase 10 quality spotcheck to generate report."}


@app.get("/api/papers", summary="Get Paginated & Filterable Corpus Papers")
def list_papers(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
):
    import json
    from pathlib import Path

    processed_dir = Path("data/processed")
    manifest_file = Path("data/manifest.json")
    manifest_map = {}
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_map = json.load(f)
        except Exception:
            pass

    paper_files = sorted(list(processed_dir.glob("*.json")))
    items = []

    for pf in paper_files:
        p_id = pf.stem
        m_info = manifest_map.get(p_id, {})
        title = m_info.get("title", f"Scientific Paper {p_id}")
        authors = m_info.get("authors", [])
        
        # Keyword filter
        if search:
            s_low = search.lower()
            if s_low not in p_id.lower() and s_low not in title.lower():
                continue

        try:
            with open(pf, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                sections = [s["section_name"] if isinstance(s, dict) else str(s) for s in p_data.get("sections", [])]
                chunks_count = len(p_data.get("chunks", []))
                char_count = sum(len(c.get("text", "")) for c in p_data.get("chunks", []))
        except Exception:
            sections = []
            chunks_count = 0
            char_count = 0

        items.append({
            "paper_id": p_id,
            "title": title,
            "authors": authors,
            "published": m_info.get("published", "2024-2026"),
            "sections": sections,
            "chunks_count": chunks_count,
            "char_count": char_count,
        })

    total_items = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = items[start_idx:end_idx]

    return {
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total_items + page_size - 1) // page_size),
        "papers": paginated_items,
    }


@app.get("/api/papers/{paper_id}", summary="Get Detailed Paper Data and Extracted Triplets")
def get_paper_detail(paper_id: str):
    import json
    from pathlib import Path

    processed_file = Path("data/processed") / f"{paper_id}.json"
    if not processed_file.exists():
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found in processed corpus")

    try:
        with open(processed_file, "r", encoding="utf-8") as f:
            paper_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading paper: {e}")

    # Load paper extractions if available
    extractions_file = Path("data/extractions") / f"{paper_id}.json"
    triplets = []
    if extractions_file.exists():
        try:
            with open(extractions_file, "r", encoding="utf-8") as f:
                ext_data = json.load(f)
                triplets = ext_data.get("triplets", [])
        except Exception:
            pass

    return {
        "paper_id": paper_id,
        "title": paper_data.get("title", f"Paper {paper_id}"),
        "sections": paper_data.get("sections", []),
        "chunks": paper_data.get("chunks", []),
        "triplets": triplets,
    }


@app.get("/api/verification/logs", summary="Get Verification Results & Few-Shot Dynamic Feedback")
def get_verification_logs():
    import json
    from pathlib import Path

    verif_file = Path("data/verification_results.jsonl")
    flagged_file = Path("data/flagged_triplets.jsonl")
    feedback_file = Path("data/few_shot_feedback.json")

    verifications = []
    if verif_file.exists():
        try:
            with open(verif_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        verifications.append(json.loads(line))
        except Exception as e:
            logger.warning(f"Error reading verifications: {e}")

    flagged = []
    if flagged_file.exists():
        try:
            with open(flagged_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        flagged.append(json.loads(line))
        except Exception as e:
            logger.warning(f"Error reading flagged items: {e}")

    few_shot_examples = []
    if feedback_file.exists():
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:
                feedback_data = json.load(f)
                few_shot_examples = feedback_data.get("examples", [])
        except Exception as e:
            logger.warning(f"Error reading feedback examples: {e}")

    stats = {
        "total_flagged": len(flagged),
        "total_verified": len(verifications),
        "confirmed": sum(1 for v in verifications if v.get("status") == "CONFIRMED"),
        "corrected": sum(1 for v in verifications if v.get("status") == "CORRECTED"),
        "rejected": sum(1 for v in verifications if v.get("status") == "REJECTED"),
        "active_few_shot_examples": len(few_shot_examples),
    }

    return {
        "stats": stats,
        "verification_records": verifications,
        "flagged_records": flagged,
        "few_shot_examples": few_shot_examples,
    }


@app.get("/api/history", summary="Get Query Execution History")
def get_history():
    import json
    from pathlib import Path
    hist_file = Path("data/query_history.json")
    if hist_file.exists():
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


@app.post("/api/history", summary="Append Query Execution to History")
def append_history(item: dict):
    import json
    from pathlib import Path
    hist_file = Path("data/query_history.json")
    history = []
    if hist_file.exists():
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    
    history.insert(0, item)
    history = history[:100]  # Keep last 100 queries
    try:
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.warning(f"Error saving history: {e}")
    return {"status": "saved", "count": len(history)}

