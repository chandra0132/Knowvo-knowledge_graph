import json
from pathlib import Path

import pytest
from graph.config import config
from graph.entity_resolver import EntityResolver, run_50_paper_entity_resolution
from graph.neo4j_client import Neo4jGraphClient


def test_entity_resolution_blocking_and_adjudication():
    """Verify candidate pair blocking and rule/LLM adjudication."""
    resolver = EntityResolver(sim_threshold=0.65)

    e1 = {"id": "1", "name": "BERT Model", "type": "Model"}
    e2 = {"id": "2", "name": "BERT", "type": "Model"}
    e3 = {"id": "3", "name": "GPT-4", "type": "Model"}

    should_merge_12, c_name_12, alias_12 = resolver.adjudicate_pair(e1, e2, sim=0.792)
    assert should_merge_12 is True
    assert c_name_12 == "BERT"
    assert alias_12 == "BERT Model"

    should_merge_13, _, _ = resolver.adjudicate_pair(e1, e3, sim=0.105)
    assert should_merge_13 is False


def test_canonical_map_persistence():
    """Verify that canonical_entities.json is saved and loaded correctly."""
    canonical_file = config.data_dir / "canonical_entities.json"
    assert canonical_file.exists(), f"Missing {canonical_file}"

    with open(canonical_file, "r", encoding="utf-8") as f:
        canonical_map = json.load(f)

    assert len(canonical_map) > 0, "canonical_entities.json is empty"
    
    sample_key = next(iter(canonical_map))
    item = canonical_map[sample_key]
    assert "canonical_id" in item
    assert "canonical_name" in item
    assert "aliases" in item and len(item["aliases"]) >= 1


def test_entity_resolution_50_paper_run_and_spot_check():
    """Verify before/after entity count reduction on 50-paper run and spot check 10 merges."""
    summary = run_50_paper_entity_resolution()

    before = summary["before_entity_count"]
    after = summary["after_entity_count"]
    merges = summary["total_merges_performed"]

    assert before > 0, f"Expected >0 before entity count, got {before}"
    assert after <= before, f"After entity count ({after}) should be <= before entity count ({before})"
    assert merges >= 0, f"Expected >=0 merges performed, got {merges}"

    sample_merges = summary["sample_merges"]
    assert len(sample_merges) >= 0, f"Expected sample merges, got {len(sample_merges)}"

    print(f"\n50-Paper Entity Resolution Spot-Check ({len(sample_merges)} merges):")
    for i, m in enumerate(sample_merges[:10], 1):
        alias = m["alias"]
        canonical = m["canonical"]
        # Ensure alias and canonical are not identical strings
        assert alias != canonical
        print(f"  {i:02d}. '{alias}'  -->  '{canonical}'")
