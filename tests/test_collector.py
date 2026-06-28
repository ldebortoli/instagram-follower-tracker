import json

import pytest

from seguidores.collector import CollectionError, ExportCollector


def _entry(username):
    return {"string_list_data": [{"value": username, "timestamp": 0}]}


def test_export_collector_reads_nested_json_files(tmp_path):
    relationships = tmp_path / "connections" / "followers_and_following"
    relationships.mkdir(parents=True)
    (relationships / "followers_1.json").write_text(
        json.dumps([_entry("Alice"), _entry("Bob")]), encoding="utf-8"
    )
    (relationships / "following.json").write_text(
        json.dumps({"relationships_following": [_entry("bob"), _entry("Carol")]}),
        encoding="utf-8",
    )

    graph = ExportCollector().collect_directory(tmp_path)

    assert graph.followers == frozenset({"alice", "bob"})
    assert graph.following == frozenset({"bob", "carol"})


def test_export_collector_requires_both_relationship_files(tmp_path):
    (tmp_path / "followers_1.json").write_text("[]", encoding="utf-8")

    with pytest.raises(CollectionError, match="following.json"):
        ExportCollector().collect_directory(tmp_path)
