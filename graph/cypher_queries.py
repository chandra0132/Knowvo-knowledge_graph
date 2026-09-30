import logging
from typing import Dict, List, Optional
from graph.neo4j_client import Neo4jGraphClient

logger = logging.getLogger("cypher_queries")


def query_hallucination_mitigation_methods(
    client: Neo4jGraphClient,
) -> List[Dict]:
    """
    Query 1: Find methods and techniques that mitigate or address LLM Hallucination / Factuality.
    
    Cypher:
    MATCH (m:Entity)-[r]->(target:Entity)
    WHERE type(r) IN ['MITIGATES', 'DETECTION_OF', 'IMPROVES', 'PROPOSES']
      AND (target.name CONTAINS 'Hallucination' OR target.name CONTAINS 'Error' OR target.name CONTAINS 'Ambiguity')
    RETURN m.name AS method, m.type AS method_type, type(r) AS relation, target.name AS target_problem, r.evidence_span AS evidence, r.paper_id AS paper_id
    """
    query = """
    MATCH (m:Entity)-[r]->(target:Entity)
    WHERE type(r) IN ['MITIGATES', 'DETECTION_OF', 'IMPROVES', 'PROPOSES']
      AND (toLower(target.name) CONTAINS 'hallucination' 
           OR toLower(target.name) CONTAINS 'error' 
           OR toLower(target.name) CONTAINS 'ambiguity')
    RETURN m.name AS method, 
           m.type AS method_type, 
           type(r) AS relation, 
           target.name AS target_problem, 
           r.evidence_span AS evidence, 
           r.paper_id AS paper_id
    LIMIT 25
    """
    with client.driver.session(database=client.database) as session:
        result = session.run(query)
        records = [dict(rec) for rec in result]
    return records


def query_model_architecture_lineage(
    client: Neo4jGraphClient, keyword: str = "LLM"
) -> List[Dict]:
    """
    Query 2: Find models/methods built on or extending baselines/architectures.
    
    Cypher:
    MATCH (m:Entity)-[r:BUILDS_ON|EXTENDS|USES]->(base:Entity)
    WHERE toLower(base.name) CONTAINS toLower($keyword) OR toLower(m.name) CONTAINS toLower($keyword)
    RETURN m.name AS method, m.type AS method_type, type(r) AS relation, base.name AS base_technology, r.evidence_span AS evidence, r.paper_id AS paper_id
    """
    query = """
    MATCH (m:Entity)-[r:BUILDS_ON|EXTENDS|USES]->(base:Entity)
    WHERE toLower(base.name) CONTAINS toLower($keyword) OR toLower(m.name) CONTAINS toLower($keyword)
    RETURN m.name AS method, 
           m.type AS method_type, 
           type(r) AS relation, 
           base.name AS base_technology, 
           r.evidence_span AS evidence, 
           r.paper_id AS paper_id
    LIMIT 25
    """
    with client.driver.session(database=client.database) as session:
        result = session.run(query, keyword=keyword)
        records = [dict(rec) for rec in result]
    return records


def query_method_evaluations_and_comparisons(
    client: Neo4jGraphClient,
) -> List[Dict]:
    """
    Query 3: Find benchmarks, evaluations, and baseline comparisons across methods.
    
    Cypher:
    MATCH (m:Entity)-[r:EVALUATES|COMPARED_WITH|IMPROVES]->(target:Entity)
    RETURN m.name AS method, type(r) AS relation, target.name AS target_benchmark_or_baseline, r.evidence_span AS evidence, r.paper_id AS paper_id
    """
    query = """
    MATCH (m:Entity)-[r:EVALUATES|COMPARED_WITH|IMPROVES]->(target:Entity)
    RETURN m.name AS method, 
           type(r) AS relation, 
           target.name AS target_benchmark_or_baseline, 
           r.evidence_span AS evidence, 
           r.paper_id AS paper_id
    LIMIT 25
    """
    with client.driver.session(database=client.database) as session:
        result = session.run(query)
        records = [dict(rec) for rec in result]
    return records
