from datetime import datetime


def calculate_timestamp_duration(
    start_timestamp: str | None,
    end_timestamp: str | None,
) -> float | None:
    """Calculate duration between two ISO timestamps in hours."""
    if not start_timestamp or not end_timestamp:
        return None

    start = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_timestamp.replace("Z", "+00:00"))

    duration_seconds = (end - start).total_seconds()

    if duration_seconds < 0:
        return None

    return round(duration_seconds / 3600, 2)


def classify_deployment_status(deployment: dict) -> str:
    """Classify a GitHub deployment using its latest status."""
    status = (deployment.get("latest_status") or "").lower()

    if status in {"success", "succeeded"}:
        return "successful"

    if status in {"failure", "failed", "error"}:
        return "failed"

    if status in {"cancelled", "canceled"}:
        return "cancelled"

    if status in {"in_progress", "queued", "pending", "waiting"}:
        return "in_progress"

    if not status:
        return "unknown"

    return status


def get_deployment_attempt_timeline(
    deployment: dict,
) -> dict:
    """Convert a deployment record into a normalized timeline."""
    created_at = deployment.get("created_at")
    status_created_at = deployment.get("status_created_at")

    status = classify_deployment_status(deployment)

    return {
        "deployment_id": deployment.get("id"),
        "environment": deployment.get("environment"),
        "ref": deployment.get("ref"),
        "sha": deployment.get("sha"),
        "created_at": created_at,
        "status": status,
        "status_created_at": status_created_at,
        "duration_hours": calculate_timestamp_duration(
            created_at,
            status_created_at,
        ),
        "environment_url": deployment.get("environment_url"),
        "url": deployment.get("url"),
    }


def get_feature_deployment_timeline(
    feature_evidence: dict,
    deployments: list[dict],
) -> dict:
    """
    Build deployment attempts associated with a feature.

    A deployment is considered related when its SHA or ref matches
    evidence from the feature branch or its pull requests.
    """
    branch_data = feature_evidence.get("branch") or {}
    branch_name = branch_data.get("name")

    development = feature_evidence.get("development") or {}
    feature_shas = set()

    first_sha = development.get("first_commit_sha")
    last_sha = development.get("last_commit_sha")

    if first_sha:
        feature_shas.add(first_sha)

    if last_sha:
        feature_shas.add(last_sha)

    for pull_request in feature_evidence.get("pull_requests",[],):
        head_sha = pull_request.get("head_sha")

        if head_sha:
            feature_shas.add(head_sha)

        merge_sha = pull_request.get(
            "merge_commit_sha"
        )

        if merge_sha:
            feature_shas.add(merge_sha)

        for commit in pull_request.get(
            "pr_commits",
            [],
        ):
            sha = commit.get("sha")

            if sha:
                feature_shas.add(sha)

    matched_deployments = []

    for deployment in deployments:
        deployment_sha = deployment.get("sha")
        deployment_ref = deployment.get("ref")

        sha_match = (
            deployment_sha
            and deployment_sha in feature_shas
        )

        ref_match = (
            branch_name
            and deployment_ref == branch_name
        )

        if sha_match or ref_match:
            matched_deployments.append(
                get_deployment_attempt_timeline(
                    deployment
                )
            )

    matched_deployments.sort(
        key=lambda item: item.get("created_at") or ""
    )

    successful_deployments = [
        deployment
        for deployment in matched_deployments
        if deployment.get("status") == "successful"
    ]

    first_successful_deployment = (
        successful_deployments[0]
        if successful_deployments
        else None
    )

    return {
        "deployment_attempt_count": len(matched_deployments),
        "successful_deployment_count": len(
            successful_deployments
        ),
        "failed_deployment_count": len([
            deployment
            for deployment in matched_deployments
            if deployment.get("status") == "failed"
        ]),
        "deployments": matched_deployments,
        "first_successful_deployment": first_successful_deployment,
        "first_successful_deployment_at": (
            first_successful_deployment.get("status_created_at")
            if first_successful_deployment
            else None
        ),
    }

def classify_deployment_environment(deployment: dict) -> str:
    """
    Classify a deployment as DEV, TEST, PROD, or UNKNOWN.

    Evidence is taken from:
    - GitHub deployment environment
    - deployment ref
    - deployment URL
    """
    environment = (deployment.get("environment") or "").lower()
    ref = (deployment.get("ref") or "").lower()
    environment_url = (
        deployment.get("environment_url") or ""
    ).lower()

    evidence = " ".join(
        [
            environment,
            ref,
            environment_url,
        ]
    )

    # Production indicators
    if any(
        value in evidence
        for value in [
            "production",
            "prod",
            "live",
        ]
    ):
        return "PROD"

    # Test / staging indicators
    if any(
        value in evidence
        for value in [
            "test",
            "testing",
            "qa",
            "staging",
            "stage",
            "uat",
        ]
    ):
        return "TEST"

    # Development indicators
    if any(
        value in evidence
        for value in [
            "development",
            "develop",
            "dev",
        ]
    ):
        return "DEV"

    return "UNKNOWN"

# ============================================================
# Deployment environment analysis
# ============================================================

def get_environment_evidence(deployment: dict) -> dict:
    """
    Return the evidence used to determine a deployment environment.
    """
    environment = deployment.get("environment")
    ref = deployment.get("ref")
    environment_url = deployment.get("environment_url")

    return {
        "environment": environment,
        "ref": ref,
        "environment_url": environment_url,
    }


def classify_deployment_environment(deployment: dict) -> dict:
    """
    Classify a deployment as DEV, TEST, PROD, or UNKNOWN.

    Uses multiple pieces of evidence:
    - GitHub deployment environment
    - deployment ref
    - environment URL
    """
    environment = (
        deployment.get("environment") or ""
    ).lower()

    ref = (
        deployment.get("ref") or ""
    ).lower()

    environment_url = (
        deployment.get("environment_url") or ""
    ).lower()

    evidence_text = " ".join(
        [
            environment,
            ref,
            environment_url,
        ]
    )

    # Production indicators
    production_indicators = [
        "production",
        "prod",
        "live",
    ]

    if any(
        indicator in evidence_text
        for indicator in production_indicators
    ):
        return {
            "environment": "PROD",
            "confidence": "high"
            if environment
            in {"production", "prod"}
            else "medium",
            "evidence": get_environment_evidence(
                deployment
            ),
        }

    # Test indicators
    test_indicators = [
        "testing",
        "test",
        "qa",
        "staging",
        "stage",
        "uat",
    ]

    if any(
        indicator in evidence_text
        for indicator in test_indicators
    ):
        return {
            "environment": "TEST",
            "confidence": "high"
            if environment
            in {
                "test",
                "testing",
                "qa",
                "staging",
                "stage",
                "uat",
            }
            else "medium",
            "evidence": get_environment_evidence(
                deployment
            ),
        }

    # Development indicators
    development_indicators = [
        "development",
        "develop",
        "dev",
    ]

    if any(
        indicator in evidence_text
        for indicator in development_indicators
    ):
        return {
            "environment": "DEV",
            "confidence": "high"
            if environment
            in {
                "development",
                "develop",
                "dev",
            }
            else "medium",
            "evidence": get_environment_evidence(
                deployment
            ),
        }

    return {
        "environment": "UNKNOWN",
        "confidence": "low",
        "evidence": get_environment_evidence(
            deployment
        ),
    }


# ============================================================
# Deployment normalization
# ============================================================

def normalize_feature_deployments(
    deployment_timeline: dict,
) -> list[dict]:
    """
    Add normalized environment information to deployment attempts.
    """
    deployments = deployment_timeline.get(
        "deployments",
        [],
    )

    normalized = []

    for deployment in deployments:
        environment_info = classify_deployment_environment(
            deployment
        )

        normalized_deployment = dict(deployment)

        normalized_deployment[
            "environment"
        ] = environment_info["environment"]

        normalized_deployment[
            "environment_confidence"
        ] = environment_info["confidence"]

        normalized_deployment[
            "environment_evidence"
        ] = environment_info["evidence"]

        normalized.append(
            normalized_deployment
        )

    return normalized


# ============================================================
# Successful deployment selection
# ============================================================

def get_first_successful_environment_deployment(
    deployments: list[dict],
    environment: str,
) -> dict | None:
    """
    Return the first successful deployment for an environment.
    """
    environment = environment.upper()

    candidates = [
        deployment
        for deployment in deployments
        if deployment.get("environment") == environment
        and deployment.get("status") == "successful"
    ]

    candidates.sort(
        key=lambda deployment:
        deployment.get("status_created_at")
        or deployment.get("created_at")
        or ""
    )

    return candidates[0] if candidates else None


def get_environment_deployment_summary(
    deployments: list[dict],
) -> dict:
    """
    Summarize first successful DEV, TEST and PROD deployments.
    """
    dev = get_first_successful_environment_deployment(
        deployments,
        "DEV",
    )

    test = get_first_successful_environment_deployment(
        deployments,
        "TEST",
    )

    prod = get_first_successful_environment_deployment(
        deployments,
        "PROD",
    )

    return {
        "dev": dev,
        "test": test,
        "prod": prod,
        "dev_deployed": dev is not None,
        "test_deployed": test is not None,
        "prod_deployed": prod is not None,
    }


# ============================================================
# Stage lead-time calculations
# ============================================================

def calculate_feature_stage_durations(
    development,
    environment_summary,
    merge_status=None,
):
    merge_status = merge_status or {}

    dev = environment_summary.get("dev") or {}
    test = environment_summary.get("test") or {}
    prod = environment_summary.get("prod") or {}

    development_start = development.get(
        "start_timestamp"
    )

    development_end = development.get(
        "end_timestamp"
    )

    merge_timestamp = merge_status.get(
        "merge_timestamp"
    )

    dev_deployed_at = dev.get(
        "status_created_at"
    )

    test_deployed_at = test.get(
        "status_created_at"
    )

    prod_deployed_at = prod.get(
        "status_created_at"
    )

    return {
        "feature_development_hours": (
            calculate_timestamp_duration(
                development_start,
                development_end,
            )
        ),

        "merge_to_dev_hours": (
            calculate_timestamp_duration(
                merge_timestamp,
                dev_deployed_at,
            )
        ),

        "dev_to_test_hours": (
            calculate_timestamp_duration(
                dev_deployed_at,
                test_deployed_at,
            )
        ),

        "test_to_prod_hours": (
            calculate_timestamp_duration(
                test_deployed_at,
                prod_deployed_at,
            )
        ),

        "development_to_prod_hours": (
            calculate_timestamp_duration(
                development_start,
                prod_deployed_at,
            )
        ),
    }


# ============================================================
# End-to-end lifecycle
# ============================================================

def build_feature_lifecycle_summary(
    feature_evidence,
    review_timeline,
    deployment_timeline,
):
    from analysis.feature_identification import (
        get_feature_development_timeline,
    )

    development = get_feature_development_timeline(
        feature_evidence
    )

    deployment_items = (
        deployment_timeline.get("deployments", [])
        if isinstance(deployment_timeline, dict)
        else deployment_timeline
    )

    environment_summary = get_environment_deployment_summary(
        deployment_items
    )

    merge_status = feature_evidence.get(
        "merge_status"
    ) or {}

    stage_durations = calculate_feature_stage_durations(
        development,
        environment_summary,
        merge_status,
    )

    first_successful_deployment = (
        get_first_successful_deployment(
            deployment_items
        )
    )

    first_successful_deployment_at = (
        first_successful_deployment.get("status_created_at")
        if first_successful_deployment
        else None
    )

    end_to_end_hours = calculate_timestamp_duration(
        development.get("start_timestamp"),
        first_successful_deployment_at,
    )

    complete_lifecycle = all(
        [
            development.get("start_timestamp"),
            development.get("end_timestamp"),
            merge_status.get("merged"),
            environment_summary.get("dev_deployed"),
            environment_summary.get("test_deployed"),
            environment_summary.get("prod_deployed"),
        ]
    )

    return {
        "complete_lifecycle": complete_lifecycle,
        "development": development,
        "review": review_timeline,
        "merge": merge_status,
        "deployments": deployment_timeline,
        "environment_summary": environment_summary,
        "stage_durations": stage_durations,
        "end_to_end_hours": end_to_end_hours,
        "first_successful_deployment_at": (
            first_successful_deployment_at
        ),
    }


# ============================================================
# Lifecycle status
# ============================================================

def get_feature_lifecycle_status(
    feature_evidence,
    review_timeline,
    deployment_timeline,
):
    from analysis.feature_identification import (
        get_feature_development_timeline,
    )

    development = get_feature_development_timeline(
        feature_evidence
    )

    pull_requests = feature_evidence.get(
        "pull_requests",
        []
    )

    merge_status = feature_evidence.get(
        "merge_status"
    ) or {}

    deployment_items = (
        deployment_timeline.get("deployments", [])
        if isinstance(deployment_timeline, dict)
        else deployment_timeline
    )

    environment_summary = get_environment_deployment_summary(
        deployment_items
    )

    development_started = bool(
        development.get("start_timestamp")
    )

    development_completed = bool(
        development.get("end_timestamp")
    )

    pull_request_created = len(
        pull_requests
    ) > 0

    pull_request_reviewed = any(
        (
            pull_request.get("review_count", 0) > 0
            or len(
                pull_request.get("reviews", [])
            ) > 0
        )
        for pull_request in pull_requests
    )

    pull_request_approved = any(
        (
            pull_request.get("approval_count", 0) > 0
            or any(
                review.get("state") == "APPROVED"
                for review in pull_request.get(
                    "reviews",
                    []
                )
            )
        )
        for pull_request in pull_requests
    )

    merged = bool(
        merge_status.get("merged")
    )

    dev_deployed = bool(
        environment_summary.get("dev_deployed")
    )

    test_deployed = bool(
        environment_summary.get("test_deployed")
    )

    prod_deployed = bool(
        environment_summary.get("prod_deployed")
    )

    complete = all(
        [
            development_started,
            development_completed,
            pull_request_created,
            merged,
            dev_deployed,
            test_deployed,
            prod_deployed,
        ]
    )

    return {
        "development_started": development_started,
        "development_completed": development_completed,
        "pull_request_created": pull_request_created,
        "pull_request_reviewed": pull_request_reviewed,
        "pull_request_approved": pull_request_approved,
        "merged": merged,
        "dev_deployed": dev_deployed,
        "test_deployed": test_deployed,
        "prod_deployed": prod_deployed,
        "complete": complete,
    }


# ============================================================
# Complete feature lifecycle builder
# ============================================================

def analyze_feature_lifecycle(
    feature_evidence: dict,
    review_timeline: dict,
    deployments: list[dict],
) -> dict:
    """
    Build the complete lifecycle analysis for a feature.

    This is the main entry point for feature lifecycle analysis.
    """

    deployment_timeline = (
        get_feature_deployment_timeline(
            feature_evidence,
            deployments,
        )
    )

    # Normalize deployment environments before calculating
    # DEV / TEST / PROD lifecycle stages.
    normalized_deployments = (
        normalize_feature_deployments(
            deployment_timeline
        )
    )

    deployment_timeline[
        "deployments"
    ] = normalized_deployments

    lifecycle = build_feature_lifecycle_summary(
        feature_evidence,
        review_timeline,
        deployment_timeline,
    )

    status = get_feature_lifecycle_status(
        feature_evidence,
        review_timeline,
        deployment_timeline,
    )

    return {
        "status": status,
        "lifecycle": lifecycle,
        "deployment_timeline": deployment_timeline,
    }

def get_deployment_attempt_summary(
    deployments: list[dict],
) -> dict:
    """
    Summarize deployment attempts by status.
    """
    successful = [
        deployment
        for deployment in deployments
        if deployment.get("status") == "successful"
    ]

    failed = [
        deployment
        for deployment in deployments
        if deployment.get("status") == "failed"
    ]

    cancelled = [
        deployment
        for deployment in deployments
        if deployment.get("status") == "cancelled"
    ]

    in_progress = [
        deployment
        for deployment in deployments
        if deployment.get("status") == "in_progress"
    ]

    return {
        "total_attempts": len(deployments),
        "successful_attempts": len(successful),
        "failed_attempts": len(failed),
        "cancelled_attempts": len(cancelled),
        "in_progress_attempts": len(in_progress),
    }


def get_environment_attempts(
    deployments: list[dict],
) -> dict:
    """
    Group deployment attempts by environment.
    """
    result = {
        "DEV": [],
        "TEST": [],
        "PROD": [],
        "UNKNOWN": [],
    }

    for deployment in deployments:
        environment = (
            deployment.get("environment")
            or "UNKNOWN"
        )

        if environment not in result:
            environment = "UNKNOWN"

        result[environment].append(
            deployment
        )

    return result


def get_first_successful_deployment(
    deployments: list[dict],
) -> dict | None:
    """
    Return the first successful deployment across
    all environments.
    """
    successful = [
        deployment
        for deployment in deployments
        if deployment.get("status") == "successful"
    ]

    successful.sort(
        key=lambda deployment:
        deployment.get("status_created_at")
        or deployment.get("created_at")
        or ""
    )

    return successful[0] if successful else None


def get_feature_deployment_summary(
    deployment_timeline: dict,
) -> dict:
    """
    Produce a compact deployment summary.
    """
    deployments = deployment_timeline.get(
        "deployments",
        [],
    )

    first_successful = (
        get_first_successful_deployment(
            deployments
        )
    )

    return {
        "attempts":
            get_deployment_attempt_summary(
                deployments
            ),

        "environments":
            get_environment_attempts(
                deployments
            ),

        "first_successful_deployment":
            first_successful,

        "first_successful_deployment_at": (
            first_successful.get(
                "status_created_at"
            )
            if first_successful
            else None
        ),
    }


def get_feature_completion_reason(
    feature_evidence: dict,
    lifecycle: dict,
) -> str:
    """
    Explain why a feature is complete or incomplete.
    """

    if lifecycle.get("complete_lifecycle"):
        return "complete"

    missing = []

    development = (
        lifecycle.get("development")
        or {}
    )

    if not development.get(
        "start_timestamp"
    ):
        missing.append(
            "development_start"
        )

    if not development.get(
        "end_timestamp"
    ):
        missing.append(
            "development_end"
        )

    merged = bool(
        (
            lifecycle.get("merge")
            or {}
        ).get("merged")
    )

    if not merged:
        missing.append("merge")

    environment_summary = (
        lifecycle.get(
            "environment_summary"
        )
        or {}
    )

    if not environment_summary.get(
        "dev_deployed"
    ):
        missing.append(
            "DEV_deployment"
        )

    if not environment_summary.get(
        "test_deployed"
    ):
        missing.append(
            "TEST_deployment"
        )

    if not environment_summary.get(
        "prod_deployed"
    ):
        missing.append(
            "PROD_deployment"
        )

    if not missing:
        return "incomplete_unknown_reason"

    return "missing: " + ", ".join(missing)

def build_complete_feature_analysis(
    feature_evidence: dict,
    review_timeline: dict,
    deployments: list[dict],
    feature_name: str | None = None,
) -> dict:
    """
    Build the complete analysis for a single feature.

    feature_name is optional because raw feature evidence may not
    contain an explicit feature_name. In that case, the branch name
    is used as the fallback identifier.
    """

    lifecycle_analysis = analyze_feature_lifecycle(
        feature_evidence,
        review_timeline,
        deployments,
    )

    completion_reason = get_feature_completion_reason(
        feature_evidence,
        lifecycle_analysis["lifecycle"],
    )

    if not feature_name:
        feature_name = feature_evidence.get("feature_name")

    if not feature_name:
        branch_data = feature_evidence.get("branch") or {}

        if isinstance(branch_data, dict):
            feature_name = branch_data.get("name")
        else:
            feature_name = branch_data

    return {
        "feature_name": feature_name,
        "branch": feature_evidence.get("branch"),
        "lifecycle": lifecycle_analysis["lifecycle"],
        "status": lifecycle_analysis["status"],
        "deployment_timeline": lifecycle_analysis["deployment_timeline"],
        "completion_reason": completion_reason,
    }


def analyze_repository_features(
    feature_results: list[dict],
    deployments: list[dict],
) -> dict:
    """
    Analyze multiple identified features and produce
    repository-level lifecycle and lead-time data.

    Accepts either:
    1. Raw feature evidence dictionaries
    2. Feature identification results containing an "evidence" field

    Python performs all calculations.
    """

    from analysis.feature_identification import (
        get_feature_review_timeline,
    )

    from analysis.metrics import (
        calculate_final_repository_analysis,
    )

    analyzed_features = []

    for feature_result in feature_results:

        # Support both input formats:
        #
        # Raw feature evidence:
        # {
        #     "feature_name": ...,
        #     "branch": ...,
        #     ...
        # }
        #
        # Wrapped feature result:
        # {
        #     "evidence": {
        #         "feature_name": ...,
        #         "branch": ...,
        #         ...
        #     }
        # }
        feature_evidence = (
            feature_result.get("evidence")
            if isinstance(feature_result, dict)
            and feature_result.get("evidence")
            else feature_result
        )

        # Preserve an explicit feature name when available.
        # For raw evidence without a feature_name, use the branch
        # name as the fallback identifier.
        feature_name = None

        if isinstance(feature_result, dict):
            feature_name = feature_result.get("feature_name")

        if not feature_name:
            feature_name = feature_evidence.get("feature_name")

        if not feature_name:
            branch_data = feature_evidence.get("branch") or {}

            if isinstance(branch_data, dict):
                feature_name = branch_data.get("name")
            else:
                feature_name = branch_data

        review_timeline = get_feature_review_timeline(
            feature_evidence
        )

        feature_analysis = build_complete_feature_analysis(
            feature_evidence,
            review_timeline,
            deployments,
            feature_name=feature_name,
        )

        analyzed_features.append(
            feature_analysis
        )

    repository_analysis = calculate_final_repository_analysis(
        analyzed_features
    )

    return {
        "feature_count": len(analyzed_features),
        "features": analyzed_features,
        "repository_analysis": repository_analysis,
    }