from __future__ import annotations

from collections import Counter, defaultdict

from gcp_network_adk.schemas import NormalisedInsight, RecommendationItem


def summarise_insights(insights: list[NormalisedInsight]) -> dict:
    by_severity = Counter(item.severity for item in insights)
    by_type = Counter(item.insight_type for item in insights)
    by_project = Counter(item.project_id for item in insights)

    resources_by_project: dict[str, set[str]] = defaultdict(set)
    for item in insights:
        for resource in item.target_resources:
            resources_by_project[item.project_id].add(resource)

    return {
        "total": len(insights),
        "by_project": dict(by_project),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "resources_by_project": {
            key: sorted(value) for key, value in resources_by_project.items()
        },
    }


def summarise_recommendations(recommendations: list[RecommendationItem]) -> dict:
    by_project = Counter(item.project_id for item in recommendations)
    by_risk = Counter(item.risk_level for item in recommendations)
    return {
        "total_recommendations": len(recommendations),
        "by_project": dict(by_project),
        "by_risk": dict(by_risk),
    }