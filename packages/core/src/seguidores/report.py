from __future__ import annotations

from seguidores.models import Comparison

MAX_NAMES_PER_SECTION = 50


def format_report(
    comparison: Comparison,
    *,
    max_names_per_section: int | None = MAX_NAMES_PER_SECTION,
) -> str:
    header = [
        f"Instagram · @{comparison.username}",
        comparison.captured_at.astimezone().strftime("%Y-%m-%d %H:%M %Z"),
    ]
    summary = [
        f"Seguidores: {len(comparison.followers)}",
        f"Seguidos: {len(comparison.following)}",
        f"No te siguen de vuelta: {len(comparison.not_following_back)}",
        f"No seguís de vuelta: {len(comparison.not_followed_back)}",
    ]
    sections: list[str] = []
    if comparison.is_baseline:
        sections.append("Primera captura guardada como línea de base.")
    else:
        sections.extend(
            [
                _section("Dejaron de seguirte", comparison.lost_followers, max_names_per_section),
                _section("Empezaron a seguirte", comparison.new_followers, max_names_per_section),
                _section(
                    "Dejaste de seguir", comparison.unfollowed_accounts, max_names_per_section
                ),
                _section(
                    "Empezaste a seguir",
                    comparison.newly_followed_accounts,
                    max_names_per_section,
                ),
            ]
        )
    sections.extend(
        [
            _section(
                "No te siguen de vuelta", comparison.not_following_back, max_names_per_section
            ),
            _section("No seguís de vuelta", comparison.not_followed_back, max_names_per_section),
        ]
    )
    return "\n\n".join(("\n".join(header), "\n".join(summary), *sections))


def format_popup(comparison: Comparison) -> str:
    if comparison.is_baseline:
        change = "Primera captura guardada."
    else:
        change = (
            f"Dejaron de seguirte: {len(comparison.lost_followers)} · "
            f"Nuevos: {len(comparison.new_followers)}"
        )
    return (
        f"@{comparison.username}\n{change}\n"
        f"No te siguen de vuelta: {len(comparison.not_following_back)}\n"
        f"No seguís de vuelta: {len(comparison.not_followed_back)}"
    )


def _section(title: str, values: frozenset[str], limit: int | None) -> str:
    names = sorted(values)
    if not names:
        return f"{title}: 0"
    visible = names if limit is None else names[:limit]
    rendered = ", ".join(f"@{name}" for name in visible)
    remaining = len(names) - len(visible)
    suffix = f" … y {remaining} más" if remaining else ""
    return f"{title} ({len(names)}): {rendered}{suffix}"
