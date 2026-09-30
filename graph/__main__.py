import json
from graph.neo4j_client import Neo4jGraphClient
from graph.cypher_queries import (
    query_hallucination_mitigation_methods,
    query_model_architecture_lineage,
    query_method_evaluations_and_comparisons,
)


def main():
    with Neo4jGraphClient() as client:
        client.clear_graph()
        ingested = client.ingest_from_file()
        stats = client.get_graph_stats()

        print(f"\n================ Neo4j Graph Ingestion ================")
        print(f"Ingested Triplets: {ingested}")
        print(f"Graph Stats: {json.dumps(stats, indent=2)}")

        print("\n================ Query 1: Hallucination & Error Mitigation ================")
        q1 = query_hallucination_mitigation_methods(client)
        for r in q1[:5]:
            print(f"  ({r['method']}) --[{r['relation']}]--> ({r['target_problem']}) | Paper: {r['paper_id']}")

        print("\n================ Query 2: Architecture Lineage (LLM/RAG/Transformer) ================")
        q2 = query_model_architecture_lineage(client, "LLM")
        for r in q2[:5]:
            print(f"  ({r['method']}) --[{r['relation']}]--> ({r['base_technology']}) | Paper: {r['paper_id']}")

        print("\n================ Query 3: Evaluations & Baseline Comparisons ================")
        q3 = query_method_evaluations_and_comparisons(client)
        for r in q3[:5]:
            print(f"  ({r['method']}) --[{r['relation']}]--> ({r['target_benchmark_or_baseline']}) | Paper: {r['paper_id']}")


if __name__ == "__main__":
    main()
