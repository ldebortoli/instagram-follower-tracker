from datetime import UTC, datetime

from seguidores.models import SocialGraph, compare_graphs
from seguidores.report import format_report


def test_report_separates_detailed_categories_with_blank_lines():
    comparison = compare_graphs(
        account_name="personal",
        username="owner",
        previous=SocialGraph.from_iterables(
            ["lost", "retained"],
            ["unfollowed", "still-following"],
        ),
        current=SocialGraph.from_iterables(
            ["retained", "new-follower"],
            ["still-following", "newly-followed"],
        ),
        captured_at=datetime(2026, 6, 30, 12, tzinfo=UTC),
    )

    report = format_report(comparison)

    expected_titles = (
        "Dejaron de seguirte",
        "Empezaron a seguirte",
        "Dejaste de seguir",
        "Empezaste a seguir",
        "No te siguen de vuelta",
        "No seguís de vuelta",
    )
    blocks = report.split("\n\n")
    detailed_sections = blocks[2:]
    assert len(detailed_sections) == len(expected_titles)
    for section, title in zip(detailed_sections, expected_titles, strict=True):
        assert section.startswith(title)
