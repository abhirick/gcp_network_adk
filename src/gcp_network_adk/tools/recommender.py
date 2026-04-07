from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import google.auth
import google.auth.transport.requests
import requests
from requests import Response
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from gcp_network_adk.config import settings
from gcp_network_adk.constants import DEFAULT_ALLOWED_STATES, NETWORK_ANALYZER_INSIGHT_TYPES
from gcp_network_adk.exceptions import InvalidScanRequestError, RecommenderApiError
from gcp_network_adk.formatters import summarise_insights
from gcp_network_adk.logging_config import get_logger
from gcp_network_adk.schemas import NormalisedInsight, ScanRequest, ScanResult

logger = get_logger(__name__)

RECOMMENDER_BASE_URL = "https://recommender.googleapis.com/v1"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def _map_severity(raw: str | None) -> str:
    if not raw:
        return "UNKNOWN"
    value = raw.upper()
    return value if value in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "UNKNOWN"


def _map_state(raw: str | None) -> str:
    if not raw:
        return "UNKNOWN"
    value = raw.upper()
    return value if value in {"ACTIVE", "ACCEPTED", "DISMISSED"} else "UNKNOWN"


def _extract_target_resources(insight: dict[str, Any]) -> list[str]:
    resources: list[str] = []
    content = insight.get("content", {}) or {}

    candidate_keys = ["targetResources", "resources", "affectedResources"]
    for key in candidate_keys:
        value = content.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str):
                resources.append(item)
            elif isinstance(item, dict):
                resource_name = item.get("resource") or item.get("name") or item.get("uri")
                if resource_name:
                    resources.append(resource_name)

    return list(dict.fromkeys(resources))


def _get_access_token() -> str:
    logger.debug("Fetching Application Default Credentials token")
    credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token


def _build_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
)
def _http_get(url: str, params: dict[str, Any]) -> Response:
    logger.info("Calling Recommender API url=%s params=%s", url, params)
    response = requests.get(
        url=url,
        headers=_build_headers(),
        params=params,
        timeout=settings.http_timeout_seconds,
    )
    return response


def _normalise_insight(
    project_id: str,
    location: str,
    insight_type: str,
    payload: dict[str, Any],
) -> NormalisedInsight:
    state_info = payload.get("stateInfo", {}) or {}
    content = payload.get("content", {}) or {}
    severity = payload.get("severity") or content.get("severity") or content.get("priority")

    recommendation_hint = (
        content.get("recommendation")
        or content.get("resolution")
        or content.get("possibleAction")
    )

    return NormalisedInsight(
        project_id=project_id,
        location=location,
        insight_id=payload.get("name", "").split("/")[-1],
        insight_name=payload.get("name", ""),
        insight_type=insight_type,
        subtype=payload.get("insightSubtype"),
        category=payload.get("category"),
        severity=_map_severity(severity),
        state=_map_state(state_info.get("state")),
        description=payload.get("description", "No description returned by API."),
        target_resources=_extract_target_resources(payload),
        content=content,
        last_refresh_time=payload.get("lastRefreshTime"),
        raw_etag=payload.get("etag"),
        recommendation_hint=recommendation_hint,
    )


def list_network_analyzer_insights(
    project_id: str,
    location: str = "global",
    insight_type: str = "google.networkanalyzer.vpcnetwork.connectivityInsight",
    max_results: int = 100,
    include_accepted: bool = False,
    include_dismissed: bool = False,
) -> dict[str, Any]:
    if not project_id.strip():
        raise InvalidScanRequestError("project_id is required")

    allowed_states = list(DEFAULT_ALLOWED_STATES)
    if include_accepted:
        allowed_states.append("ACCEPTED")
    if include_dismissed:
        allowed_states.append("DISMISSED")

    state_filter = " OR ".join(
        [f'stateInfo.state = "{state}"' for state in sorted(set(allowed_states))]
    )

    url = (
        f"{RECOMMENDER_BASE_URL}/projects/{project_id}/locations/"
        f"{location}/insightTypes/{insight_type}/insights"
    )
    params: dict[str, Any] = {
        "pageSize": min(max_results, 1000),
        "filter": state_filter,
    }

    response = _http_get(url=url, params=params)

    if not response.ok:
        logger.error(
            "Recommender API failed project_id=%s insight_type=%s status=%s body=%s",
            project_id,
            insight_type,
            response.status_code,
            response.text,
        )
        raise RecommenderApiError(
            f"Recommender API returned {response.status_code} for "
            f"project_id={project_id}, insight_type={insight_type}"
        )

    payload = response.json()
    raw_items = payload.get("insights", []) or []
    normalised = [
        _normalise_insight(project_id, location, insight_type, item)
        for item in raw_items
    ]

    logger.info(
        "Fetched %s insights for project_id=%s insight_type=%s",
        len(normalised),
        project_id,
        insight_type,
    )

    return {
        "project_id": project_id,
        "location": location,
        "insight_type": insight_type,
        "count": len(normalised),
        "insights": [item.model_dump() for item in normalised],
        "next_page_token": payload.get("nextPageToken"),
    }


def scan_projects_network_insights(
    project_ids: list[str],
    location: str = "global",
    insight_types: list[str] | None = None,
    max_results_per_type: int = 100,
    include_accepted: bool = False,
    include_dismissed: bool = False,
) -> dict[str, Any]:
    request = ScanRequest(
        project_ids=project_ids,
        location=location,
        insight_types=insight_types or [],
        max_results_per_type=max_results_per_type,
        include_accepted=include_accepted,
        include_dismissed=include_dismissed,
    )

    selected_insight_types = request.insight_types or NETWORK_ANALYZER_INSIGHT_TYPES
    collected: list[NormalisedInsight] = []

    logger.info(
        "Starting scan projects=%s location=%s insight_types=%s",
        request.project_ids,
        request.location,
        selected_insight_types,
    )

    for project_id in request.project_ids:
        for insight_type in selected_insight_types:
            try:
                result = list_network_analyzer_insights(
                    project_id=project_id,
                    location=request.location,
                    insight_type=insight_type,
                    max_results=request.max_results_per_type,
                    include_accepted=request.include_accepted,
                    include_dismissed=request.include_dismissed,
                )
                collected.extend(
                    [NormalisedInsight(**item) for item in result["insights"]]
                )
            except Exception as exc:
                logger.exception(
                    "Failed to fetch project_id=%s insight_type=%s",
                    project_id,
                    insight_type,
                )
                collected.append(
                    NormalisedInsight(
                        project_id=project_id,
                        location=request.location,
                        insight_id=f"error-{project_id}-{insight_type}",
                        insight_name="",
                        insight_type=insight_type,
                        subtype="API_ERROR",
                        category="PLATFORM",
                        severity="UNKNOWN",
                        state="UNKNOWN",
                        description=str(exc),
                        target_resources=[],
                        content={"error": str(exc)},
                        last_refresh_time=None,
                        raw_etag=None,
                        recommendation_hint=None,
                    )
                )

    scan_result = ScanResult(
        scan_scope={
            "project_ids": request.project_ids,
            "location": request.location,
            "insight_types": selected_insight_types,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        insights=collected,
        stats=summarise_insights(collected),
    )

    logger.info("Scan complete total_insights=%s", len(collected))
    return scan_result.model_dump()


def scan_request_to_json(
    project_ids: list[str],
    location: str = "global",
    insight_types: list[str] | None = None,
    max_results_per_type: int = 100,
    include_accepted: bool = False,
    include_dismissed: bool = False,
) -> str:
    result = scan_projects_network_insights(
        project_ids=project_ids,
        location=location,
        insight_types=insight_types,
        max_results_per_type=max_results_per_type,
        include_accepted=include_accepted,
        include_dismissed=include_dismissed,
    )
    return json.dumps(result, indent=2)