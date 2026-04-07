from __future__ import annotations

import json

from gcp_network_adk.formatters import summarise_recommendations
from gcp_network_adk.logging_config import get_logger
from gcp_network_adk.schemas import NormalisedInsight, RecommendationBatch, RecommendationItem

logger = get_logger(__name__)


def _default_validation_steps() -> list[str]:
    return [
        "Re-run the same Network Analyzer scan.",
        "Review the affected resource in the Google Cloud console.",
        "Confirm effective routes, firewall evaluation, and backend health as relevant.",
        "Run Connectivity Tests for reachability or path issues.",
    ]


def _default_rollback_plan() -> list[str]:
    return [
        "Revert the most recent network configuration change.",
        "Restore the previous IaC state or prior route / firewall rule.",
        "Re-check traffic path and service health after rollback.",
    ]


def _build_recommendation(insight: NormalisedInsight) -> RecommendationItem:
    subtype = (insight.subtype or "").upper()
    description = insight.description

    likely_root_cause = "Configuration mismatch or unintended network dependency."
    recommended_action = (
        "Review the finding details and apply the smallest safe configuration change."
    )
    why_this_fix = (
        "This is the generic fallback recommendation because the subtype did not match a "
        "specific remediation playbook."
    )
    risk_level = "medium"
    confidence = 0.60
    commands: list[str] = []
    terraform_notes: list[str] = []

    if "API_ERROR" in subtype:
        likely_root_cause = "The collector could not retrieve the source insight payload."
        recommended_action = (
            "Check IAM permissions, API enablement, project ID validity, and supported insight types."
        )
        why_this_fix = "Without a valid payload, safe remediation guidance cannot be generated."
        risk_level = "low"
        confidence = 0.95
        commands = [
            "gcloud services enable recommender.googleapis.com --project=<PROJECT_ID>",
        ]

    elif "FIREWALL" in subtype:
        likely_root_cause = (
            "A deny rule, a missing allow rule, or incorrect target / source selection is blocking traffic."
        )
        recommended_action = (
            "Review firewall direction, priority, target tags, service accounts, and protocol / port rules."
        )
        why_this_fix = "Firewall-related findings usually come from policy evaluation blocking intended traffic."
        risk_level = "medium"
        confidence = 0.90
        commands = [
            "gcloud compute firewall-rules list --project=<PROJECT_ID>",
            "gcloud compute instances list --project=<PROJECT_ID>",
        ]
        terraform_notes = [
            "Review google_compute_firewall priority, direction, target_tags, source_ranges, and allow / deny blocks."
        ]

    elif "ROUTE" in subtype or "SHADOW" in subtype:
        likely_root_cause = "A higher-priority or overlapping route is overriding the intended route."
        recommended_action = (
            "Inspect custom routes, subnet routes, and peering-imported routes. "
            "Adjust priority, destination range, or next hop."
        )
        why_this_fix = "Route shadowing changes the effective path and often breaks expected connectivity."
        risk_level = "medium"
        confidence = 0.88
        commands = [
            "gcloud compute routes list --project=<PROJECT_ID>",
            "gcloud compute networks peerings list --project=<PROJECT_ID>",
        ]
        terraform_notes = [
            "Review google_compute_route priority, destination_range, and next_hop settings."
        ]

    elif "LOAD_BALANCER" in subtype or "LOADBALANCER" in subtype:
        likely_root_cause = (
            "The backend service, forwarding rule, proxy, NEG, or health check configuration is inconsistent."
        )
        recommended_action = (
            "Review backend health, health check ports and paths, NEG membership, and forwarding rule alignment."
        )
        why_this_fix = "Load balancer issues commonly come from unhealthy backends or mismatched resources."
        risk_level = "high"
        confidence = 0.84
        commands = [
            "gcloud compute backend-services list --project=<PROJECT_ID>",
            "gcloud compute health-checks list --project=<PROJECT_ID>",
        ]
        terraform_notes = [
            "Review backend service, URL map, target proxy, forwarding rule, and health check resources together."
        ]

    elif "IP" in subtype or "ADDRESS" in subtype:
        likely_root_cause = "IP space is constrained, fragmented, or incorrectly allocated."
        recommended_action = (
            "Review subnet sizing, secondary ranges, reserved ranges, and unused allocations."
        )
        why_this_fix = "IP-related insights usually signal exhaustion or inefficient address planning."
        risk_level = "high"
        confidence = 0.82
        commands = [
            "gcloud compute networks subnets list --project=<PROJECT_ID>",
        ]
        terraform_notes = [
            "Review subnet CIDRs, secondary ranges, and private service access allocations."
        ]

    elif "GOOGLE_SERVICE" in subtype or "PRIVATE_SERVICE" in subtype:
        likely_root_cause = (
            "Private access or managed service connectivity settings are incomplete or inconsistent."
        )
        recommended_action = (
            "Check Private Google Access, PSC configuration, DNS, forwarding rules, and route export settings."
        )
        why_this_fix = "Managed service reachability often depends on several aligned controls."
        risk_level = "medium"
        confidence = 0.80
        commands = [
            "gcloud compute forwarding-rules list --project=<PROJECT_ID>",
            "gcloud compute networks subnets list --project=<PROJECT_ID>",
        ]

    return RecommendationItem(
        insight_id=insight.insight_id,
        project_id=insight.project_id,
        problem_summary=description,
        likely_root_cause=likely_root_cause,
        recommended_action=recommended_action,
        why_this_fix=why_this_fix,
        risk_level=risk_level,  # type: ignore[arg-type]
        confidence=confidence,
        validation_steps=_default_validation_steps(),
        rollback_plan=_default_rollback_plan(),
        commands=commands,
        terraform_notes=terraform_notes,
        needs_human_review=True,
    )


def generate_fix_suggestions(scan_result_json: str) -> str:
    logger.info("Generating remediation suggestions from collector output")
    payload = json.loads(scan_result_json)
    raw_insights = payload.get("insights", []) or []
    insights = [NormalisedInsight(**item) for item in raw_insights]

    recommendations = [_build_recommendation(item) for item in insights]
    grouped_summary = summarise_recommendations(recommendations)

    batch = RecommendationBatch(
        recommendations=recommendations,
        grouped_summary=grouped_summary,
    )

    logger.info("Generated %s remediation items", len(recommendations))
    return batch.model_dump_json(indent=2)