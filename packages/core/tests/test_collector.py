import json

import pytest
from seguidores.collector import CollectionError, ExportCollector


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_collect_files_supports_instagram_follower_and_following_formats(tmp_path):
    followers = write_json(
        tmp_path / "followers_1.json",
        [
            {"string_list_data": [{"value": "Alice", "href": "https://www.instagram.com/alice/"}]},
            {
                "title": "Bob",
                "string_list_data": [{"href": "https://www.instagram.com/_u/bob"}],
            },
        ],
    )
    following = write_json(
        tmp_path / "following.json",
        {
            "relationships_following": [
                {
                    "title": "alice",
                    "string_list_data": [{"href": "https://www.instagram.com/_u/alice"}],
                },
                {
                    "title": "Carol",
                    "string_list_data": [{"href": "https://www.instagram.com/_u/carol"}],
                },
            ]
        },
    )

    graph = ExportCollector().collect_files([followers], [following])

    assert graph.followers == frozenset({"alice", "bob"})
    assert graph.following == frozenset({"alice", "carol"})


def test_collect_files_rejects_threads_export_with_clear_error(tmp_path):
    threads = write_json(
        tmp_path / "followers.json",
        {
            "text_post_app_text_post_app_followers": [
                {"string_list_data": [{"value": "alice", "href": "https://www.threads.com/alice"}]}
            ]
        },
    )
    following = write_json(tmp_path / "following.json", {"relationships_following": []})

    with pytest.raises(CollectionError, match="Threads, no a Instagram"):
        ExportCollector().collect_files([threads], [following])


def test_collect_files_rejects_swapped_or_unknown_files(tmp_path):
    wrong = write_json(tmp_path / "wrong.json", {"relationships_following": []})
    following = write_json(tmp_path / "following.json", {"relationships_following": []})

    with pytest.raises(CollectionError, match="no parece ser un archivo de followers"):
        ExportCollector().collect_files([wrong], [following])


def test_collect_directory_combines_split_follower_files(tmp_path):
    write_json(
        tmp_path / "followers_1.json",
        [{"string_list_data": [{"value": "alice"}]}],
    )
    write_json(
        tmp_path / "followers_2.json",
        [{"string_list_data": [{"value": "bob"}]}],
    )
    write_json(
        tmp_path / "following.json",
        {"relationships_following": [{"title": "alice", "string_list_data": []}]},
    )

    graph = ExportCollector().collect_directory(tmp_path)

    assert graph.followers == frozenset({"alice", "bob"})
    assert graph.following == frozenset({"alice"})
