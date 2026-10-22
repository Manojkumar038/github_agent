from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from tools.actions import get_github_actions_runs
from tools.branches import get_github_branches
from tools.commits import get_github_commits
from tools.deployments import get_github_deployments
from tools.pull_requests import (
    get_github_pull_request,
    get_github_pull_request_commits,
    get_github_pull_requests,
    get_github_pull_request_reviews,
)
from tools.commits import get_github_commit_details
from tools.releases import get_github_releases, get_github_tags
from tools.repository import get_github_repo_info


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


def days_between(start: Any, end: Any) -> float | None:
    hours = hours_between(start, end)
    if hours is None:
        return None
    return round(hours / 24, 2)


def calculate_pull_request_lifecycle(pr: dict, reviews: list[dict]) -> dict:
    submitted_reviews = [
        review for review in reviews
        if review.get("submitted_at") and parse_time(review.get("submitted_at"))
    ]
    submitted_reviews.sort(key=lambda review: parse_time(review["submitted_at"]))
    first_review_at = submitted_reviews[0]["submitted_at"] if submitted_reviews else None

    approvals = [
        review for review in submitted_reviews
        if (review.get("state") or "").upper() == "APPROVED"
    ]
    first_approval_at = approvals[0]["submitted_at"] if approvals else None
    created_at = pr.get("created_at")
    merged_at = pr.get("merged_at")

    return {
        "first_review_at": first_review_at,
        "first_approval_at": first_approval_at,
        "created_to_first_review_hours": hours_between(created_at, first_review_at),
        "created_to_first_review_days": days_between(created_at, first_review_at),
        "first_review_to_approval_hours": hours_between(first_review_at, first_approval_at),
        "first_review_to_approval_days": days_between(first_review_at, first_approval_at),
        "approval_to_merge_hours": hours_between(first_approval_at, merged_at),
        "approval_to_merge_days": days_between(first_approval_at, merged_at),
        "created_to_merge_hours": hours_between(created_at, merged_at),
        "created_to_merge_days": days_between(created_at, merged_at),
        "review_count": len(submitted_reviews),
        "approval_count": len(approvals),
        "changes_requested_count": sum(
            1 for review in submitted_reviews
            if (review.get("state") or "").upper() == "CHANGES_REQUESTED"
        ),
        "timing_note": (
            "Durations are elapsed calendar time between GitHub timestamps; "
            "they do not measure active reviewer effort."
        ),
    }


def build_pull_request_analysis_payload(
    repository_url: str,
    pull_number: int,
    max_patch_chars: int = 24000,
) -> dict:
    """Collect review timing and bounded per-commit diff evidence for one PR."""
    owner, repo = parse_repository_url(repository_url)
    pull_request = get_github_pull_request(owner, repo, pull_number)
    review_data = get_github_pull_request_reviews(owner, repo, pull_number)
    commit_data = get_github_pull_request_commits(owner, repo, pull_number)
    reviews = review_data.get("reviews", [])
    commits = commit_data.get("commits", [])
    lifecycle = calculate_pull_request_lifecycle(pull_request, reviews)

    detailed_commits = []
    remaining_patch_chars = max(0, max_patch_chars)
    warnings = []

    for commit in commits:
        sha = commit.get("sha")
        if not sha:
            continue

        try:
            details = get_github_commit_details(owner, repo, sha)
        except Exception as exc:
            warnings.append(f"Could not fetch details for commit {sha[:7]}: {exc}")
            details = {**commit, "changed_files": [], "changed_file_count": 0}

        files = []
        for changed_file in details.get("changed_files", []):
            item = {key: value for key, value in changed_file.items() if key != "patch"}
            patch = changed_file.get("patch")
            if isinstance(patch, str) and remaining_patch_chars:
                included_patch = patch[:remaining_patch_chars]
                item["patch"] = included_patch
                remaining_patch_chars -= len(included_patch)
                item["patch_truncated"] = len(included_patch) < len(patch)
            elif isinstance(patch, str):
                item["patch"] = ""
                item["patch_truncated"] = True
            files.append(item)

        detailed_commits.append({
            "sha": details.get("sha") or sha,
            "message": details.get("message") or commit.get("message"),
            "author": commit.get("author"),
            "date": details.get("date") or commit.get("date"),
            "url": details.get("url") or commit.get("url"),
            "changed_file_count": details.get("changed_file_count", len(files)),
            "additions": sum(item.get("additions") or 0 for item in files),
            "deletions": sum(item.get("deletions") or 0 for item in files),
            "changed_files": files,
        })

    return {
        "repository": {"owner": owner, "name": repo},
        "pull_request": {
            **pull_request,
            "lifecycle": lifecycle,
            "reviews": reviews,
            "commits": detailed_commits,
            "commit_count": commit_data.get("commit_count", len(commits)),
        },
        "analysis_guidance": (
            "Assess commit and code practices only from the supplied messages, file changes, "
            "patches, and review evidence. Cite commit/file evidence; treat heuristics as "
            "signals, not proof of inefficiency. Patches may be truncated."
        ),
        "patch_character_limit": max_patch_chars,
        "warnings": warnings,
    }


def _is_probable_feature_branch(branch_name: str, default_branch: str | None) -> bool:
    if not branch_name:
        return False

    if default_branch and branch_name == default_branch:
        return False

    normalized = branch_name.strip().lower()
    excluded_exact = {
        "main",
        "master",
        "develop",
        "development",
        "dev",
        "test",
        "testing",
        "qa",
        "staging",
        "stage",
        "production",
        "prod",
    }

    if normalized in excluded_exact:
        return False

    if normalized.startswith(("dependabot/", "renovate/", "refs/")):
        return False

    return True


def _extract_commit_timestamp(commit: dict) -> str | None:
    if not isinstance(commit, dict):
        return None

    timestamp = (
        commit.get("date")
        or commit.get("committer_date")
        or commit.get("author_date")
        or commit.get("timestamp")
    )
    if timestamp:
        return timestamp

    commit_data = commit.get("commit")
    if isinstance(commit_data, dict):
        author = commit_data.get("author")
        if isinstance(author, dict) and author.get("date"):
            return author.get("date")

        committer = commit_data.get("committer")
        if isinstance(committer, dict) and committer.get("date"):
            return committer.get("date")

    return None


def _extract_commit_author(commit: dict) -> str | None:
    if not isinstance(commit, dict):
        return None

    author = commit.get("author")
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return author.get("login") or author.get("name")

    commit_data = commit.get("commit")
    if isinstance(commit_data, dict):
        commit_author = commit_data.get("author")
        if isinstance(commit_author, dict):
            return commit_author.get("name") or commit_author.get("email")

    return None


def _is_bot_commit(commit: dict) -> bool:
    if not isinstance(commit, dict):
        return True

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
    bot_markers = ("[bot]", "dependabot", "renovate", "github-actions", "github action")
    return any(marker in candidate for candidate in normalized for marker in bot_markers)


def _normalize_commit(commit: dict) -> dict:
    timestamp = _extract_commit_timestamp(commit)
    author = _extract_commit_author(commit)
    return {
        "sha": commit.get("sha"),
        "message": (commit.get("message") or commit.get("commit", {}).get("message")),
        "author": author,
        "author_login": commit.get("author", {}).get("login") if isinstance(commit.get("author"), dict) else None,
        "author_email": (commit.get("commit", {}).get("author", {}).get("email")),
        "timestamp": timestamp,
        "is_bot": _is_bot_commit(commit),
    }


def _summarize_branch_human_commits(commits: list[dict]) -> dict:
    human_commits = []
    for commit in commits:
        item = _normalize_commit(commit)
        if item["timestamp"] and not item["is_bot"]:
            human_commits.append(item)

    human_commits.sort(key=lambda item: parse_time(item["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc))

    if not human_commits:
        return {
            "first_human_commit_at": None,
            "last_human_commit_at": None,
            "human_commit_count": 0,
            "developers": [],
            "bot_commit_count": 0,
            "feature_lead_time_hours": None,
            "feature_lead_time_days": None,
        }

    first = human_commits[0]
    last = human_commits[-1]
    developers = sorted({item["author"] for item in human_commits if item.get("author")})
    lead_hours = hours_between(first["timestamp"], last["timestamp"])
    developer_commits: dict[str, list[dict]] = {}
    for commit in human_commits:
        if commit.get("author"):
            developer_commits.setdefault(commit["author"], []).append(commit)

    developer_activity = []
    for developer, commits_by_developer in sorted(developer_commits.items()):
        commits_by_developer.sort(
            key=lambda item: parse_time(item["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc)
        )
        first_commit_at = commits_by_developer[0]["timestamp"]
        last_commit_at = commits_by_developer[-1]["timestamp"]
        activity_hours = hours_between(first_commit_at, last_commit_at)
        developer_activity.append({
            "developer": developer,
            "human_commit_count": len(commits_by_developer),
            "first_commit_at": first_commit_at,
            "last_commit_at": last_commit_at,
            "activity_span_hours": activity_hours,
            "activity_span_days": None if activity_hours is None else round(activity_hours / 24, 2),
        })

    return {
        "first_human_commit_at": first["timestamp"],
        "last_human_commit_at": last["timestamp"],
        "human_commit_count": len(human_commits),
        "developers": developers,
        "developer_activity": developer_activity,
        "bot_commit_count": sum(1 for commit in commits if _normalize_commit(commit).get("is_bot")),
        "feature_lead_time_hours": lead_hours,
        "feature_lead_time_days": None if lead_hours is None else round(lead_hours / 24, 2),
    }


def _normalize_environment_name(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    aliases = {
        "dev": "DEV",
        "development": "DEV",
        "develop": "DEV",
        "test": "TEST",
        "testing": "TEST",
        "qa": "TEST",
        "staging": "TEST",
        "stage": "TEST",
        "uat": "TEST",
        "prod": "PROD",
        "production": "PROD",
        "live": "PROD",
    }
    return aliases.get(normalized)


def _build_environment_summary(deployments: list[dict]) -> dict:
    env_map = {"DEV": [], "TEST": [], "PROD": []}

    for deployment in deployments:
        environment_name = deployment.get("environment") or deployment.get("ref") or ""
        normalized_environment = _normalize_environment_name(environment_name)
        if normalized_environment in env_map:
            env_map[normalized_environment].append(deployment)

    def first_successful(items: list[dict]) -> dict | None:
        successful = [
            item
            for item in items
            if (item.get("latest_status") or item.get("status") or "").lower() in {"success", "succeeded"}
        ]
        if not successful:
            return None
        successful.sort(key=lambda item: item.get("status_created_at") or item.get("created_at") or "")
        return successful[0]

    dev = first_successful(env_map["DEV"])
    test = first_successful(env_map["TEST"])
    prod = first_successful(env_map["PROD"])

    return {
        "dev": dev,
        "test": test,
        "prod": prod,
        "dev_deployed_at": dev.get("status_created_at") if dev else None,
        "test_deployed_at": test.get("status_created_at") if test else None,
        "prod_deployed_at": prod.get("status_created_at") if prod else None,
    }


def _deployment_matches_feature_branch(
    deployment: dict,
    branch_name: str,
    related_shas: set[str],
) -> bool:
    return (
        deployment.get("ref") == branch_name
        or deployment.get("sha") in related_shas
    )


def build_lead_time_payload(repository_url: str, branch_name: str | None = None) -> dict:
    owner, repo = parse_repository_url(repository_url)
    selected_branch = branch_name.strip() if isinstance(branch_name, str) and branch_name.strip() else None

    repository = get_github_repo_info(owner, repo)
    branch_result = get_github_branches(owner, repo)
    branches = branch_result.get("branches", []) if isinstance(branch_result, dict) else []
    default_branch = repository.get("default_branch") or "main"

    try:
        pull_requests = get_github_pull_requests(owner, repo, state="all").get("pull_requests", [])
    except Exception:
        pull_requests = []

    try:
        deployments = get_github_deployments(owner, repo).get("deployments", [])
    except Exception:
        deployments = []

    try:
        actions = get_github_actions_runs(owner, repo)
    except Exception:
        actions = {"run_count": 0, "runs": []}

    try:
        releases = get_github_releases(owner, repo)
    except Exception:
        releases = {"release_count": 0, "releases": []}

    try:
        tags = get_github_tags(owner, repo)
    except Exception:
        tags = {"tag_count": 0, "tags": []}

    feature_branches: list[dict] = []
    for branch in branches:
        if not isinstance(branch, dict):
            continue

        current_branch = branch.get("name")
        if not current_branch or current_branch == default_branch:
            continue

        if not _is_probable_feature_branch(current_branch, default_branch):
            continue

        if selected_branch and current_branch != selected_branch:
            continue

        branch_commits = get_github_commits(owner, repo, current_branch).get("commits", [])
        branch_summary = _summarize_branch_human_commits(branch_commits)

        branch_pull_requests = [
            pr for pr in pull_requests if (pr.get("source_branch") or "") == current_branch
        ]

        related_shas = {
            sha
            for pr in branch_pull_requests
            for sha in (pr.get("source_sha"), pr.get("merge_commit_sha"))
            if sha
        }
        if branch.get("sha"):
            related_shas.add(branch["sha"])

        branch_deployments = [
            deployment
            for deployment in deployments
            if _deployment_matches_feature_branch(
                deployment,
                current_branch,
                related_shas,
            )
        ]

        environment_summary = _build_environment_summary(branch_deployments)
        merge_timestamps = [
            pr.get("merged_at") for pr in branch_pull_requests if pr.get("merged_at")
        ]
        merge_timestamp = min(merge_timestamps) if merge_timestamps else None

        feature_payload = {
            "branch_name": current_branch,
            "base_branch": default_branch,
            "branch_sha": branch.get("sha"),
            "developers": branch_summary["developers"],
            "developer_activity": branch_summary["developer_activity"],
            "first_human_commit_at": branch_summary["first_human_commit_at"],
            "last_human_commit_at": branch_summary["last_human_commit_at"],
            "human_commit_count": branch_summary["human_commit_count"],
            "bot_commit_count": branch_summary["bot_commit_count"],
            "feature_lead_time_hours": branch_summary["feature_lead_time_hours"],
            "feature_lead_time_days": branch_summary["feature_lead_time_days"],
            "pull_requests": [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "state": pr.get("state"),
                    "created_at": pr.get("created_at"),
                    "merged_at": pr.get("merged_at"),
                    "author": pr.get("author"),
                    "source_branch": pr.get("source_branch"),
                    "target_branch": pr.get("target_branch"),
                }
                for pr in branch_pull_requests
            ],
            "deployments": [
                {
                    "deployment_id": deployment.get("id"),
                    "environment": deployment.get("environment"),
                    "status": deployment.get("latest_status") or deployment.get("status"),
                    "created_at": deployment.get("created_at"),
                    "status_created_at": deployment.get("status_created_at"),
                    "ref": deployment.get("ref"),
                    "sha": deployment.get("sha"),
                    "url": deployment.get("url"),
                }
                for deployment in branch_deployments
            ],
            "environment_summary": {
                "deployment_match_basis": "feature branch ref, branch tip SHA, or associated PR source/merge SHA",
                "matched_deployment_count": len(branch_deployments),
                "dev_deployed_at": environment_summary["dev_deployed_at"],
                "test_deployed_at": environment_summary["test_deployed_at"],
                "prod_deployed_at": environment_summary["prod_deployed_at"],
                "merge_to_dev_hours": hours_between(merge_timestamp, environment_summary["dev_deployed_at"]),
                "merge_to_dev_days": days_between(merge_timestamp, environment_summary["dev_deployed_at"]),
                "dev_to_test_hours": hours_between(environment_summary["dev_deployed_at"], environment_summary["test_deployed_at"]),
                "dev_to_test_days": days_between(environment_summary["dev_deployed_at"], environment_summary["test_deployed_at"]),
                "test_to_prod_hours": hours_between(environment_summary["test_deployed_at"], environment_summary["prod_deployed_at"]),
                "test_to_prod_days": days_between(environment_summary["test_deployed_at"], environment_summary["prod_deployed_at"]),
                "development_to_prod_hours": hours_between(branch_summary["first_human_commit_at"], environment_summary["prod_deployed_at"]),
                "development_to_prod_days": days_between(branch_summary["first_human_commit_at"], environment_summary["prod_deployed_at"]),
            },
        }
        feature_branches.append(feature_payload)

    if selected_branch:
        pull_requests = [
            pr for pr in pull_requests if (pr.get("source_branch") or "") == selected_branch
        ]
        deployments = [
            deployment
            for deployment in deployments
            if (deployment.get("ref") == selected_branch)
            or (deployment.get("sha") == next((b.get("sha") for b in branches if isinstance(b, dict) and b.get("name") == selected_branch), None))
        ]

    project_payload = {
        "repository": {
            "owner": owner,
            "repo": repo,
            "full_name": repository.get("full_name") or f"{owner}/{repo}",
            "default_branch": default_branch,
            "url": repository.get("url") or f"https://github.com/{owner}/{repo}",
        },
        "project_lead_time_hours": None,
        "project_first_human_commit_at": None,
        "project_last_human_commit_at": None,
        "project_human_commit_count": 0,
        "project_developers": [],
        "branch_count": len(branches),
    }

    if selected_branch:
        project_payload["selected_branch"] = selected_branch
        project_payload["scope"] = "single_feature_branch"
    else:
        default_branch_commits = get_github_commits(owner, repo, default_branch).get("commits", [])
        project_summary = _summarize_branch_human_commits(default_branch_commits)
        project_payload["project_lead_time_hours"] = project_summary.get("feature_lead_time_hours")
        project_payload["project_first_human_commit_at"] = project_summary.get("first_human_commit_at")
        project_payload["project_last_human_commit_at"] = project_summary.get("last_human_commit_at")
        project_payload["project_human_commit_count"] = project_summary.get("human_commit_count")
        project_payload["project_developers"] = project_summary.get("developers", [])

    return {
        "repository": project_payload["repository"],
        "project": project_payload,
        "feature_branches": feature_branches,
        "pull_requests": {
            "pull_request_count": len(pull_requests),
            "pull_requests": [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "state": pr.get("state"),
                    "created_at": pr.get("created_at"),
                    "merged_at": pr.get("merged_at"),
                    "source_branch": pr.get("source_branch"),
                    "target_branch": pr.get("target_branch"),
                    "author": pr.get("author"),
                }
                for pr in pull_requests
            ],
        },
        "delivery": {
            "actions": {
                "workflow_count": actions.get("workflow_count", 0),
                "runs": actions.get("runs", []),
                "run_count": actions.get("run_count", len(actions.get("runs", []))),
            },
            "deployments": {
                "deployment_count": len(deployments),
                "deployments": [
                    {
                        "deployment_id": item.get("id"),
                        "environment": item.get("environment"),
                        "status": item.get("latest_status") or item.get("status"),
                        "created_at": item.get("created_at"),
                        "status_created_at": item.get("status_created_at"),
                        "ref": item.get("ref"),
                        "sha": item.get("sha"),
                        "environment_url": item.get("environment_url"),
                    }
                    for item in deployments
                ],
            },
        },
        "releases": releases,
        "tags": tags,
    }
