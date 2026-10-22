"""
GitHub Development Lead-Time Report Generator

Generates a small, deterministic report using repository metadata,
branches, and commits only.

Development lead time:
    last meaningful HUMAN commit - first meaningful HUMAN commit

Bot/automation commits are excluded from lead-time calculations.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.repository import get_github_repo_info
from tools.branches import get_github_branches
from tools.commits import get_github_commits
from tools.pull_requests import get_github_pull_requests
from tools.deployments import get_github_deployments
from tools.actions import get_github_actions_info, get_github_actions_runs
from tools.releases import get_github_releases, get_github_tags


def parse_repository_url(value: str) -> tuple[str, str]:
    value = value.strip()
    if not value:
        raise ValueError("Repository URL is required.")

    if re.fullmatch(r"[^/\s]+/[^/\s]+", value):
        owner, repo = value.split("/", 1)
        return owner, repo.removesuffix(".git")

    parsed = urlparse(value)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Only GitHub repository URLs are supported.")

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL.")

    return parts[0], parts[1].removesuffix(".git")


def parse_time(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def hours_between(start: Any, end: Any) -> float | None:
    start_time = parse_time(start)
    end_time = parse_time(end)
    if not start_time or not end_time:
        return None

    hours = (end_time - start_time).total_seconds() / 3600
    return round(max(0.0, hours), 2)


def hours_to_days(hours: float | int | None) -> float | None:
    if hours is None:
        return None
    return round(float(hours) / 24, 2)


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return round(values[0], 2)

    position = (len(values) - 1) * percentile_value / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower

    result = values[lower] + (values[upper] - values[lower]) * fraction
    return round(result, 2)


def build_distribution(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "average_hours": None,
            "median_hours": None,
            "p75_hours": None,
            "p90_hours": None,
        }

    return {
        "count": len(values),
        "average_hours": round(mean(values), 2),
        "median_hours": round(median(values), 2),
        "p75_hours": percentile(values, 75),
        "p90_hours": percentile(values, 90),
    }


def is_probable_feature_branch(
    branch_name: str,
    default_branch: str | None,
) -> bool:
    if not branch_name:
        return False

    if default_branch and branch_name == default_branch:
        return False

    normalized = branch_name.strip().lower()

    excluded_exact = {
        "main", "master", "develop", "development", "dev",
        "test", "testing", "qa", "staging", "stage",
        "production", "prod",
    }

    if normalized in excluded_exact:
        return False

    if normalized.startswith(("dependabot/", "renovate/", "refs/")):
        return False

    return True


def get_commit_timestamp(commit: dict) -> str | None:
    direct_date = commit.get("date") or commit.get("author_date")
    if direct_date:
        return direct_date

    committer_date = commit.get("committer_date")
    if committer_date:
        return committer_date

    commit_data = commit.get("commit")
    if isinstance(commit_data, dict):
        author = commit_data.get("author")
        if isinstance(author, dict) and author.get("date"):
            return author["date"]

        committer = commit_data.get("committer")
        if isinstance(committer, dict) and committer.get("date"):
            return committer["date"]

    return None


def get_commit_author(commit: dict) -> str | None:
    author = commit.get("author")

    if isinstance(author, str):
        return author

    if isinstance(author, dict):
        return author.get("login") or author.get("name")

    commit_data = commit.get("commit")
    if isinstance(commit_data, dict):
        commit_author = commit_data.get("author")
        if isinstance(commit_author, dict):
            return (
                commit_author.get("name")
                or commit_author.get("email")
            )

    return None


def is_bot_commit(commit: dict) -> bool:
    """
    Detect GitHub automation accounts.

    Explicitly handles common bots and the standard GitHub [bot]
    naming convention without depending on commit message content.
    """
    candidates: list[str] = []

    author = commit.get("author")
    if isinstance(author, str):
        candidates.append(author)
    elif isinstance(author, dict):
        candidates.extend(
            value for value in (
                author.get("login"),
                author.get("name"),
                author.get("email"),
            )
            if value
        )

    commit_data = commit.get("commit")
    if isinstance(commit_data, dict):
        nested_author = commit_data.get("author")
        if isinstance(nested_author, dict):
            candidates.extend(
                value for value in (
                    nested_author.get("name"),
                    nested_author.get("email"),
                )
                if value
            )

    normalized = [str(value).strip().lower() for value in candidates]

    bot_markers = (
        "[bot]",
        "dependabot",
        "renovate",
        "github-actions",
        "github action",
    )

    return any(
        marker in candidate
        for candidate in normalized
        for marker in bot_markers
    )


def normalize_commit(commit: dict) -> dict | None:
    if not isinstance(commit, dict):
        return None

    timestamp = get_commit_timestamp(commit)
    if not timestamp:
        return None

    return {
        "timestamp": timestamp,
        "author": get_commit_author(commit),
        "is_bot": is_bot_commit(commit),
    }


def calculate_branch_lead_time(
    owner: str,
    repo: str,
    branch_name: str,
) -> dict:
    result = get_github_commits(owner, repo, branch_name)

    raw_commits = (
        result.get("commits", [])
        if isinstance(result, dict)
        else []
    )

    normalized_commits = []
    bot_commits_excluded = 0

    for commit in raw_commits:
        normalized = normalize_commit(commit)
        if not normalized:
            continue

        if normalized["is_bot"]:
            bot_commits_excluded += 1
            continue

        normalized_commits.append(normalized)

    if not normalized_commits:
        return {
            "branch": branch_name,
            "developers": [],
            "commit_count": 0,
            "first_commit": None,
            "last_commit": None,
            "development_lead_time_hours": None,
            "human_commits_used": 0,
            "bot_commits_excluded": bot_commits_excluded,
            "status": "insufficient_data",
        }

    normalized_commits.sort(
        key=lambda commit: (
            parse_time(commit["timestamp"])
            or datetime.min.replace(tzinfo=timezone.utc)
        )
    )

    first_commit = normalized_commits[0]
    last_commit = normalized_commits[-1]

    first_timestamp = first_commit["timestamp"]
    last_timestamp = last_commit["timestamp"]

    lead_time = hours_between(first_timestamp, last_timestamp)
    lead_days = hours_to_days(lead_time)

    developers = sorted(
        {
            commit["author"]
            for commit in normalized_commits
            if commit.get("author")
        }
    )
    commits_by_developer: dict[str, list[dict]] = {}
    for commit in normalized_commits:
        if commit.get("author"):
            commits_by_developer.setdefault(commit["author"], []).append(commit)

    developer_activity = []
    for developer, developer_commits in sorted(commits_by_developer.items()):
        developer_commits.sort(key=lambda commit: parse_time(commit["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc))
        first_developer_commit = developer_commits[0]["timestamp"]
        last_developer_commit = developer_commits[-1]["timestamp"]
        activity_hours = hours_between(first_developer_commit, last_developer_commit)
        developer_activity.append({
            "developer": developer,
            "human_commit_count": len(developer_commits),
            "first_commit": first_developer_commit,
            "last_commit": last_developer_commit,
            "activity_span_hours": activity_hours,
            "activity_span_days": hours_to_days(activity_hours),
        })

    return {
        "branch": branch_name,
        "developers": developers,
        "developer_activity": developer_activity,
        "commit_count": len(normalized_commits),
        "first_commit": first_timestamp,
        "last_commit": last_timestamp,
        "development_lead_time_hours": lead_time,
        "development_lead_time_days": lead_days,
        "human_commits_used": len(normalized_commits),
        "bot_commits_excluded": bot_commits_excluded,
        "status": (
            "calculated"
            if lead_time is not None
            else "insufficient_data"
        ),
    }


def generate_github_report(
    repository_url: str,
    output_path: str | None = None,
) -> dict:
    start_time = time.perf_counter()

    owner, repo = parse_repository_url(repository_url)
    warnings: list[str] = []

    repository = get_github_repo_info(owner, repo)
    if not isinstance(repository, dict):
        repository = {}

    repository_name = repository.get("name") or repo
    repository_full_name = (
        repository.get("full_name") or f"{owner}/{repo}"
    )
    default_branch = repository.get("default_branch") or "main"

    pull_request_result = {"pull_request_count": 0, "pull_requests": []}
    delivery_result = {
        "actions": {"has_actions": False, "workflow_count": 0, "workflows": [], "run_count": 0, "runs": []},
        "deployments": {"deployment_count": 0, "deployments": []},
    }
    releases_result = {"release_count": 0, "releases": []}
    tags_result = {"tag_count": 0, "tags": []}

    try:
        pull_request_result = get_github_pull_requests(owner, repo, state="all")
    except Exception as exc:
        warnings.append(f"Could not fetch pull requests: {exc}")

    try:
        actions_info = get_github_actions_info(owner, repo)
        actions_runs = get_github_actions_runs(owner, repo)
        if isinstance(actions_info, dict):
            actions_info.setdefault("runs", [])
            actions_info.setdefault("run_count", actions_runs.get("run_count", 0))
            actions_info.setdefault("workflow_count", actions_info.get("workflow_count", 0))
            if isinstance(actions_runs, dict):
                actions_info["runs"] = actions_runs.get("runs", [])
                actions_info["run_count"] = actions_runs.get("run_count", actions_info.get("run_count", 0))
            delivery_result["actions"] = actions_info
        else:
            delivery_result["actions"] = {"has_actions": False, "workflow_count": 0, "workflows": [], "run_count": 0, "runs": []}
    except Exception as exc:
        warnings.append(f"Could not fetch GitHub Actions data: {exc}")

    try:
        deployments_result = get_github_deployments(owner, repo)
        if isinstance(deployments_result, dict):
            delivery_result["deployments"] = deployments_result
    except Exception as exc:
        warnings.append(f"Could not fetch deployments: {exc}")

    try:
        releases_result = get_github_releases(owner, repo)
    except Exception as exc:
        warnings.append(f"Could not fetch releases: {exc}")

    try:
        tags_result = get_github_tags(owner, repo)
    except Exception as exc:
        warnings.append(f"Could not fetch tags: {exc}")

    branch_result = get_github_branches(owner, repo)
    branches = (
        branch_result.get("branches", [])
        if isinstance(branch_result, dict)
        else []
    )

    feature_branches = []

    for branch in branches:
        if not isinstance(branch, dict):
            continue

        branch_name = branch.get("name")
        if branch_name and is_probable_feature_branch(
            branch_name, default_branch
        ):
            feature_branches.append(branch_name)

    features = []

    for branch_name in feature_branches:
        try:
            feature = calculate_branch_lead_time(
                owner, repo, branch_name
            )

            feature_name = branch_name
            prefixes = (
                "feature/", "features/", "feat/",
                "bugfix/", "bug/", "fix/", "hotfix/",
                "release/", "chore/", "task/", "enhancement/",
            )

            lower_branch = branch_name.lower()
            for prefix in prefixes:
                if lower_branch.startswith(prefix):
                    feature_name = branch_name[len(prefix):]
                    break

            feature["feature"] = feature_name
            features.append(feature)

        except Exception as exc:
            warnings.append(
                f"Could not analyze branch '{branch_name}': {exc}"
            )
            features.append({
                "feature": branch_name,
                "branch": branch_name,
                "developers": [],
                "commit_count": 0,
                "first_commit": None,
                "last_commit": None,
                "development_lead_time_hours": None,
                "human_commits_used": 0,
                "bot_commits_excluded": 0,
                "status": "error",
            })

    calculated_lead_times = [
        feature["development_lead_time_hours"]
        for feature in features
        if feature.get("development_lead_time_hours") is not None
    ]
    calculated_lead_days = [
        hours_to_days(hours)
        for hours in calculated_lead_times
        if hours_to_days(hours) is not None
    ]

    developer_activity_by_name: dict[str, list[dict]] = {}

    for feature in features:
        for activity in feature.get("developer_activity", []):
            developer = activity.get("developer")
            if developer:
                developer_activity_by_name.setdefault(developer, []).append({
                    "feature": feature.get("feature"),
                    "branch": feature.get("branch"),
                    "human_commit_count": activity.get("human_commit_count", 0),
                    "first_commit": activity.get("first_commit"),
                    "last_commit": activity.get("last_commit"),
                    "activity_span_hours": activity.get("activity_span_hours"),
                    "activity_span_days": activity.get("activity_span_days"),
                })

    developer_summary = []

    for developer, feature_activity in sorted(developer_activity_by_name.items()):
        timed_activity = [
            item for item in feature_activity
            if parse_time(item.get("first_commit")) and parse_time(item.get("last_commit"))
        ]
        first_commit = min(
            (item["first_commit"] for item in timed_activity),
            key=lambda value: parse_time(value) or datetime.max.replace(tzinfo=timezone.utc),
            default=None,
        )
        last_commit = max(
            (item["last_commit"] for item in timed_activity),
            key=lambda value: parse_time(value) or datetime.min.replace(tzinfo=timezone.utc),
            default=None,
        )
        activity_span_hours = hours_between(first_commit, last_commit)
        developer_summary.append({
            "developer": developer,
            "feature_count": len(feature_activity),
            "human_commits_observed": sum(item["human_commit_count"] for item in feature_activity),
            "first_commit": first_commit,
            "last_commit": last_commit,
            "activity_span_hours": activity_span_hours,
            "activity_span_days": hours_to_days(activity_span_hours),
            "features": feature_activity,
        })

    total_bot_commits_excluded = sum(
        feature.get("bot_commits_excluded", 0)
        for feature in features
    )

    elapsed_seconds = round(time.perf_counter() - start_time, 2)

    report = {
        "report_version": "3.2-commit-plus-delivery",
        "repository": {
            "owner": owner,
            "name": repository_name,
            "full_name": repository_full_name,
            "url": repository_url,
            "default_branch": default_branch,
        },
        "definition": {
            "metric": "development_lead_time",
            "formula": "last meaningful human commit - first meaningful human commit",
            "unit": "hours",
            "feature_identification": "non-default development branch",
            "bot_commits": "excluded",
            "additional_data_sources": [
                "pull_requests",
                "deployments",
                "github_actions",
                "releases",
                "tags",
            ],
        },
        "summary": {
            "branch_count": len(branches),
            "feature_count": len(features),
            "calculated_feature_count": len(calculated_lead_times),
            "bot_commits_excluded": total_bot_commits_excluded,
            "average_lead_time_hours": (
                round(mean(calculated_lead_times), 2)
                if calculated_lead_times else None
            ),
            "average_lead_time_days": (
                round(mean(calculated_lead_days), 2)
                if calculated_lead_days else None
            ),
            "median_lead_time_hours": (
                round(median(calculated_lead_times), 2)
                if calculated_lead_times else None
            ),
            "median_lead_time_days": (
                round(median(calculated_lead_days), 2)
                if calculated_lead_days else None
            ),
            "lead_time_distribution": build_distribution(
                calculated_lead_times
            ),
        },
        "features": features,
        "developer_summary": developer_summary,
        "pull_requests": pull_request_result,
        "delivery": delivery_result,
        "releases": releases_result,
        "tags": tags_result,
        "data_quality": {
            "warnings": warnings,
            "note": (
                "Lead time is calculated from meaningful human commit timestamps, "
                "and the report also includes PR, GitHub Actions, deployment, "
                "release, and tag metadata for the repository."
            ),
            "collection_seconds": elapsed_seconds,
        },
    }

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with output_file.open("w", encoding="utf-8") as file:
            json.dump(
                report,
                file,
                indent=2,
                ensure_ascii=False,
            )

    return report


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python github_report_generator.py "
            "<github_repo_url> [output_file]"
        )
        sys.exit(1)

    repository_url = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        report = generate_github_report(repository_url, output_path)

        print(
            f"Repository: {report['repository']['full_name']}"
        )
        print(
            f"Feature branches: {report['summary']['feature_count']}"
        )
        print(
            f"Calculated lead times: "
            f"{report['summary']['calculated_feature_count']}"
        )
        print(
            f"Bot commits excluded: "
            f"{report['summary']['bot_commits_excluded']}"
        )
        print(
            f"Average development lead time: "
            f"{report['summary']['average_lead_time_hours']} hours"
        )
        print(
            f"Median development lead time: "
            f"{report['summary']['median_lead_time_hours']} hours"
        )

        if output_path:
            print(f"Report generated: {output_path}")

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
