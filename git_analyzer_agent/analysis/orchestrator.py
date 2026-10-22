from typing import Optional

from tools.repository import get_github_repo_info
from tools.branches import get_github_branches
from tools.commits import get_github_commits

from analysis.feature_identification import (
    identify_feature,
    get_feature_review_timeline,
)
from analysis.feature_lifecycle import (
    analyze_feature_lifecycle,
)


# ============================================================
# Helpers
# ============================================================

def _get_commit_timestamp(commit: dict) -> Optional[str]:
    """
    Get the commit timestamp.

    Supports the common timestamp formats returned by the
    GitHub commit tool.
    """

    if not isinstance(commit, dict):
        return None

    # Direct timestamp fields
    timestamp = (
        commit.get("committer_date")
        or commit.get("author_date")
        or commit.get("date")
        or commit.get("timestamp")
    )

    if timestamp:
        return timestamp

    # GitHub API style:
    # {
    #   "commit": {
    #       "author": {"date": "..."},
    #       "committer": {"date": "..."}
    #   }
    # }
    commit_data = commit.get("commit")

    if isinstance(commit_data, dict):

        committer = commit_data.get("committer")

        if isinstance(committer, dict) and committer.get("date"):
            return committer["date"]

        author = commit_data.get("author")

        if isinstance(author, dict) and author.get("date"):
            return author["date"]

    return None


def _parse_timestamp(timestamp: str):
    """
    Convert an ISO-8601 timestamp into datetime.
    """

    from datetime import datetime

    if not timestamp:
        return None

    try:
        return datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None


def _get_commit_message(commit: dict) -> Optional[str]:
    """
    Extract commit message from the supported commit formats.
    """

    if not isinstance(commit, dict):
        return None

    message = commit.get("message")

    if message:
        return message

    commit_data = commit.get("commit")

    if isinstance(commit_data, dict):
        message = commit_data.get("message")

        if message:
            return message

    return None


def _calculate_commit_lead_time(
    commits: list,
) -> dict:
    """
    Calculate development lead time using EVERY commit.

    Lead time:

        last commit timestamp - first commit timestamp
    """

    timestamped_commits = []

    for commit in commits:

        timestamp = _get_commit_timestamp(commit)

        if not timestamp:
            continue

        parsed_timestamp = _parse_timestamp(timestamp)

        if parsed_timestamp is None:
            continue

        timestamped_commits.append(
            {
                "sha": commit.get("sha"),
                "message": _get_commit_message(commit),
                "timestamp": timestamp,
                "parsed_timestamp": parsed_timestamp,
            }
        )

    if not timestamped_commits:
        return {
            "commit_count": 0,
            "first_commit": None,
            "last_commit": None,
            "lead_time_hours": None,
        }

    # Oldest -> newest
    timestamped_commits.sort(
        key=lambda item: item["parsed_timestamp"]
    )

    first_commit = timestamped_commits[0]
    last_commit = timestamped_commits[-1]

    duration_seconds = (
        last_commit["parsed_timestamp"]
        - first_commit["parsed_timestamp"]
    ).total_seconds()

    return {
        "commit_count": len(timestamped_commits),

        "first_commit": {
            "sha": first_commit.get("sha"),
            "message": first_commit.get("message"),
            "timestamp": first_commit.get("timestamp"),
        },

        "last_commit": {
            "sha": last_commit.get("sha"),
            "message": last_commit.get("message"),
            "timestamp": last_commit.get("timestamp"),
        },

        "lead_time_hours": round(
            max(duration_seconds, 0) / 3600,
            2,
        ),
    }


# ============================================================
# Repository report
# ============================================================

def _build_repository_report(
    repository: dict,
    default_branch: Optional[str],
    branch_count: int,
    feature_results: list,
) -> dict:
    """
    Build the compact repository lead-time report.
    """

    completed_features = [
        feature
        for feature in feature_results
        if feature.get("lead_time_hours") is not None
    ]

    lead_times = [
        feature["lead_time_hours"]
        for feature in completed_features
        if feature.get("lead_time_hours") is not None
    ]

    repository_average_lead_time = None

    if lead_times:
        repository_average_lead_time = round(
            sum(lead_times) / len(lead_times),
            2,
        )

    return {
        "repository_name": repository.get("name"),
        "repository_full_name": repository.get("full_name"),
        "repository_description": repository.get("description"),

        "default_branch": default_branch,
        "branch_count": branch_count,

        "feature_count": len(feature_results),
        "analyzed_feature_count": len(completed_features),

        "repository_average_lead_time_hours":
            repository_average_lead_time,

        "features": feature_results,
    }


# ============================================================
# Repository analysis
# ============================================================

def analyze_github_repository(
    owner: str,
    repo: str,
) -> dict:
    """
    Analyze feature development lead time.

    Lead time is calculated using ALL commits on each
    non-default branch:

        first commit timestamp
                    ↓
              ALL commits
                    ↓
        last commit timestamp

        lead time = last - first
    """

    # ========================================================
    # Step 1/4 — Repository metadata
    # ========================================================

    repository = get_github_repo_info(
        owner,
        repo,
    )

    default_branch = (
        repository.get("default_branch")
        if isinstance(repository, dict)
        else None
    )

    # ========================================================
    # Step 2/4 — Branches
    # ========================================================

    branch_result = get_github_branches(
        owner,
        repo,
    )

    branches = branch_result.get(
        "branches",
        [],
    )

    # ========================================================
    # Step 3/4 — All branch commits
    # ========================================================

    feature_results = []

    for branch in branches:

        if not isinstance(branch, dict):
            continue

        branch_name = branch.get("name")

        if not branch_name:
            continue

        # Don't treat the default branch as a feature.
        if default_branch and branch_name == default_branch:
            continue

        try:

            # Get ALL commits from this branch.
            commit_result = get_github_commits(
                owner,
                repo,
                branch_name,
            )

            # Support either:
            #
            #   [commit, commit, ...]
            #
            # or:
            #
            #   {"commits": [...]}
            #
            if isinstance(commit_result, list):

                commits = commit_result

            elif isinstance(commit_result, dict):

                commits = (
                    commit_result.get("commits")
                    or commit_result.get("items")
                    or []
                )

            else:

                commits = []

            lead_time = _calculate_commit_lead_time(
                commits
            )

            feature_results.append(
                {
                    "feature_name": branch_name,
                    "branch": branch_name,

                    "commit_count": lead_time.get(
                        "commit_count",
                        0,
                    ),

                    "first_commit": lead_time.get(
                        "first_commit"
                    ),

                    "last_commit": lead_time.get(
                        "last_commit"
                    ),

                    "lead_time_hours": lead_time.get(
                        "lead_time_hours"
                    ),
                }
            )

        except Exception as exc:

            feature_results.append(
                {
                    "feature_name": branch_name,
                    "branch": branch_name,

                    "commit_count": 0,

                    "first_commit": None,
                    "last_commit": None,

                    "lead_time_hours": None,

                    "error": str(exc),
                }
            )

    # ========================================================
    # Step 4/4 — Final report
    # ========================================================

    final_result = _build_repository_report(
        repository=repository,
        default_branch=default_branch,
        branch_count=len(branches),
        feature_results=feature_results,
    )

    return {
        "status": "completed",
        "analysis_type": "repository",
        "final_result": final_result,
    }


# ============================================================
# Single feature analysis
# ============================================================

def analyze_github_feature(
    owner: str,
    repo: str,
    feature_name: str,
) -> dict:
    """
    Analyze a specific feature.

    The existing feature lifecycle implementation is retained
    here. Repository-level analysis above uses only commit
    timestamps.
    """

    # ========================================================
    # Step 1 — Repository metadata
    # ========================================================

    repository = get_github_repo_info(
        owner,
        repo,
    )

    # ========================================================
    # Step 2 — Feature identification
    # ========================================================

    feature_result = identify_feature(
        owner=owner,
        repo=repo,
        feature_name=feature_name,
    )

    if not isinstance(feature_result, dict):
        raise ValueError(
            "Feature identification returned an invalid result."
        )

    # ========================================================
    # Missing / ambiguous feature
    # ========================================================

    if feature_result.get("match_type") in {
        "multiple_candidates",
        "no_match",
    }:

        return {
            "status": "needs_clarification",
            "analysis_type": "feature",
            "repository": repository,
            "feature_name": feature_name,
            "identification": feature_result,
        }

    # ========================================================
    # Step 3 — Feature evidence
    # ========================================================

    feature_evidence = feature_result.get(
        "evidence",
        feature_result,
    )

    # ========================================================
    # Step 4 — Review timeline
    # ========================================================

    review_timeline = get_feature_review_timeline(
        feature_evidence,
    )

    # ========================================================
    # Step 5 — Existing lifecycle analysis
    # ========================================================

    lifecycle_result = analyze_feature_lifecycle(
        feature_evidence=feature_evidence,
        review_timeline=review_timeline,
        deployments=[],
    )

    lifecycle = lifecycle_result.get(
        "lifecycle",
        {},
    )

    # ========================================================
    # Final result
    # ========================================================

    final_result = {
        "repository_name": repository.get(
            "full_name"
        ),

        "feature_name": feature_evidence.get(
            "feature_name",
            feature_name,
        ),

        "lifecycle": lifecycle,

        "status": lifecycle_result.get(
            "status",
            {},
        ),
    }

    return {
        "status": "completed",
        "analysis_type": "feature",

        "final_result": final_result,

        "repository": repository,

        "feature_name": feature_evidence.get(
            "feature_name",
            feature_name,
        ),

        "identification": feature_result,

        "lifecycle": lifecycle,

        "feature_status": lifecycle_result.get(
            "status",
            {},
        ),
    }