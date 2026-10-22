from tools.branches import get_github_branch
from tools.pull_requests import get_github_pull_requests
from tools.repository import get_github_repo_info

def identify_feature_by_branch(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Identify a feature using an exact branch name."""

    branch_data = get_github_branch(
        owner,
        repo,
        branch,
    )

    return {
        "match_type": "exact_branch",
        "feature_branch": branch_data.get("name"),
        "branch_sha": branch_data.get("sha"),
        "protected": branch_data.get("protected"),
        "confidence": "high",
    }

from tools.branches import get_github_branches


def identify_feature_by_name(
    owner: str,
    repo: str,
    feature_name: str,
) -> dict:
    """Find candidate feature branches using a feature name."""

    branches_data = get_github_branches(
        owner,
        repo,
    )

    branches = branches_data.get(
        "branches",
        [],
    )

    search_term = feature_name.strip().lower()

    matches = [
        branch
        for branch in branches
        if search_term in (
            branch.get("name") or ""
        ).lower()
    ]

    if len(matches) == 1:
        return {
            "match_type": "feature_name",
            "feature_name": feature_name,
            "feature_branch": matches[0].get("name"),
            "branch_sha": matches[0].get("sha"),
            "confidence": "medium",
            "candidates": matches,
        }

    if len(matches) > 1:
        return {
            "match_type": "multiple_candidates",
            "feature_name": feature_name,
            "feature_branch": None,
            "branch_sha": None,
            "confidence": "low",
            "candidates": matches,
        }

    return {
        "match_type": "no_match",
        "feature_name": feature_name,
        "feature_branch": None,
        "branch_sha": None,
        "confidence": "none",
        "candidates": [],
    }

def identify_feature_by_name_with_prs(
    owner: str,
    repo: str,
    feature_name: str,
) -> dict:
    """Find feature candidates using both branches and pull requests."""

    branch_result = identify_feature_by_name(
        owner,
        repo,
        feature_name,
    )

    pull_data = get_github_pull_requests(
        owner,
        repo,
        state="all",
    )

    pull_requests = pull_data.get(
        "pull_requests",
        [],
    )

    search_term = feature_name.strip().lower()

    pr_matches = [
        pull
        for pull in pull_requests
        if search_term in (
            pull.get("title") or ""
        ).lower()
        or search_term in (
            pull.get("source_branch") or ""
        ).lower()
    ]

    branch_candidates = branch_result.get(
        "candidates",
        [],
    )

    candidates = []

    for branch in branch_candidates:
        candidates.append({
            "source": "branch",
            "branch": branch.get("name"),
            "branch_sha": branch.get("sha"),
        })

    for pull in pr_matches:
        candidates.append({
            "source": "pull_request",
            "pull_number": pull.get("number"),
            "title": pull.get("title"),
            "branch": pull.get("source_branch"),
            "branch_sha": pull.get("source_sha"),
            "state": pull.get("state"),
            "merged_at": pull.get("merged_at"),
        })

    return {
        "feature_name": feature_name,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

def group_feature_candidates(
    candidates: list[dict],
) -> list[dict]:
    """Group branch and PR evidence by feature branch."""

    grouped = {}

    for candidate in candidates:
        branch = candidate.get("branch")

        if not branch:
            continue

        if branch not in grouped:
            grouped[branch] = {
                "branch": branch,
                "branch_evidence": [],
                "pull_requests": [],
            }

        if candidate.get("source") == "branch":
            grouped[branch]["branch_evidence"].append(
                candidate
            )

        elif candidate.get("source") == "pull_request":
            grouped[branch]["pull_requests"].append(
                candidate
            )

    return list(grouped.values())

def filter_feature_candidates(
    owner: str,
    repo: str,
    grouped_candidates: list[dict],
) -> list[dict]:
    """Remove repository-level branches that are not feature branches."""

    repo_info = get_github_repo_info(
        owner,
        repo,
    )

    default_branch = repo_info.get(
        "default_branch"
    )

    return [
        candidate
        for candidate in grouped_candidates
        if candidate.get("branch") != default_branch
    ]

def select_feature_candidate(
    candidates: list[dict],
) -> dict:
    """Select a feature candidate only when the result is unambiguous."""

    if not candidates:
        return {
            "match_type": "no_match",
            "selected": None,
            "candidate_count": 0,
            "candidates": [],
        }

    if len(candidates) == 1:
        candidate = candidates[0]

        return {
            "match_type": "single_candidate",
            "selected": candidate,
            "candidate_count": 1,
            "candidates": candidates,
        }

    return {
        "match_type": "multiple_candidates",
        "selected": None,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

def score_feature_candidate(
    candidate: dict,
    feature_name: str,
) -> int:
    """Score a feature candidate using available evidence."""

    score = 0

    search_term = feature_name.strip().lower()

    branch = (
        candidate.get("branch") or ""
    ).lower()

    if search_term and search_term in branch:
        score += 3

    pull_requests = candidate.get(
        "pull_requests",
        [],
    )

    for pull_request in pull_requests:
        title = (
            pull_request.get("title") or ""
        ).lower()

        if search_term and search_term in title:
            score += 3

        if pull_request.get("merged_at"):
            score += 2

        if pull_request.get("state") == "closed":
            score += 1

    if len(pull_requests) == 1:
        score += 1

    return score

def rank_feature_candidates(
    candidates: list[dict],
    feature_name: str,
) -> list[dict]:
    """Rank feature candidates by evidence strength."""

    ranked = []

    for candidate in candidates:
        scored_candidate = dict(candidate)

        scored_candidate["score"] = (
            score_feature_candidate(
                candidate,
                feature_name,
            )
        )

        ranked.append(
            scored_candidate
        )

    ranked.sort(
        key=lambda candidate: candidate.get(
            "score",
            0,
        ),
        reverse=True,
    )

    return ranked

def select_ranked_feature_candidate(
    ranked_candidates: list[dict],
) -> dict:
    """Select a ranked candidate only when the ranking is unambiguous."""

    if not ranked_candidates:
        return {
            "match_type": "no_match",
            "selected": None,
            "candidate_count": 0,
            "candidates": [],
        }

    if len(ranked_candidates) == 1:
        return {
            "match_type": "single_candidate",
            "selected": ranked_candidates[0],
            "candidate_count": 1,
            "candidates": ranked_candidates,
        }

    top_candidate = ranked_candidates[0]
    second_candidate = ranked_candidates[1]

    top_score = top_candidate.get("score", 0)
    second_score = second_candidate.get("score", 0)

    score_difference = top_score - second_score

    if score_difference >= 5:
        return {
            "match_type": "strong_candidate",
            "selected": top_candidate,
            "candidate_count": len(ranked_candidates),
            "score_difference": score_difference,
            "candidates": ranked_candidates,
        }

    return {
        "match_type": "multiple_candidates",
        "selected": None,
        "candidate_count": len(ranked_candidates),
        "score_difference": score_difference,
        "candidates": ranked_candidates,
    }

def get_feature_pull_requests(
    owner: str,
    repo: str,
    branch: str,
) -> list[dict]:
    """Return all pull requests associated with a feature branch."""

    from tools.pull_requests import (
        get_github_pull_requests_for_branch,
    )

    pull_data = get_github_pull_requests_for_branch(
        owner,
        repo,
        branch,
    )

    return pull_data.get(
        "pull_requests",
        [],
    )


def get_feature_pull_request_details(
    owner: str,
    repo: str,
    pull_requests: list[dict],
) -> list[dict]:
    """Enrich feature pull requests with reviews and commits."""

    from tools.pull_requests import (
        get_github_pull_request_reviews,
        get_github_pull_request_commits,
    )

    results = []

    for pull_request in pull_requests:
        pull_number = pull_request.get(
            "number"
        )

        if not pull_number:
            continue

        reviews = get_github_pull_request_reviews(
            owner,
            repo,
            pull_number,
        )

        commits = get_github_pull_request_commits(
            owner,
            repo,
            pull_number,
        )

        enriched = dict(pull_request)

        enriched["reviews"] = reviews.get(
            "reviews",
            [],
        )

        enriched["review_count"] = reviews.get(
            "review_count",
            0,
        )

        enriched["approval_count"] = reviews.get(
            "approval_count",
            0,
        )

        enriched["pr_commits"] = commits.get(
            "commits",
            [],
        )

        enriched["pr_commit_count"] = commits.get(
            "commit_count",
            0,
        )

        results.append(enriched)

    return results


def get_feature_branch_context(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Return branch metadata and development information.

    Historical feature branches may have been deleted after their PRs
    were created or merged, so missing branches are treated as valid
    historical evidence rather than a fatal error.
    """

    from tools.branches import get_github_branch
    from tools.repository import get_github_repo_info
    from tools.commits import (
        get_branch_development_summary,
    )

    repo_data = get_github_repo_info(
        owner,
        repo,
    )

    base_branch = repo_data.get(
        "default_branch"
    )

    try:
        branch_data = get_github_branch(
            owner,
            repo,
            branch,
        )

    except ValueError as error:
        if "not found" not in str(error).lower():
            raise

        branch_data = {
            "name": branch,
            "protected": None,
            "sha": None,
            "commit_url": None,
            "exists": False,
        }

        return {
            "branch": branch_data,
            "base_branch": base_branch,
            "development": {
                "branch": branch,
                "base_branch": base_branch,
                "commit_count": 0,
                "start_timestamp": None,
                "end_timestamp": None,
                "development_duration_hours": None,
                "first_commit_sha": None,
                "last_commit_sha": None,
            },
            "branch_exists": False,
        }

    development = get_branch_development_summary(
        owner,
        repo,
        branch,
        base_branch,
    )

    return {
        "branch": {
            **branch_data,
            "exists": True,
        },
        "base_branch": base_branch,
        "development": development,
        "branch_exists": True,
    }


def build_feature_evidence(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Build the complete evidence set for a feature branch."""

    branch_context = get_feature_branch_context(
        owner,
        repo,
        branch,
    )

    pull_requests = get_feature_pull_requests(
        owner,
        repo,
        branch,
    )

    pull_request_details = (
        get_feature_pull_request_details(
            owner,
            repo,
            pull_requests,
        )
    )

    merge_status = get_feature_merge_status(
        {
            "pull_requests": pull_request_details
        }
    )

    return {
        "branch": branch_context.get("branch"),
        "branch_exists": branch_context.get("branch_exists", False),
        "base_branch": branch_context.get("base_branch"),
        "development": branch_context.get("development"),
        "pull_requests": pull_request_details,
        "pull_request_count": len(pull_request_details),
        "merge_status": merge_status,
    }


def identify_feature(
    owner: str,
    repo: str,
    feature_name: str | None = None,
    branch: str | None = None,
) -> dict:
    """
    Identify a feature using an exact branch or feature name.

    Exact branch matching has priority.
    Feature-name matching uses ranked evidence.
    Ambiguous results are never guessed.
    """

    if branch:
        result = identify_feature_by_branch(
            owner,
            repo,
            branch,
        )

        if result.get("match_type") == "exact_branch":
            result["evidence"] = build_feature_evidence(
                owner,
                repo,
                branch,
            )

        return result

    if not feature_name:
        return {
            "match_type": "missing_input",
            "selected": None,
            "message": (
                "Provide either a feature name "
                "or an exact feature branch."
            ),
        }

    candidate_data = (
        identify_feature_by_name_with_prs(
            owner,
            repo,
            feature_name,
        )
    )

    grouped_candidates = group_feature_candidates(
        candidate_data.get(
            "candidates",
            [],
        )
    )

    filtered_candidates = filter_feature_candidates(
        owner,
        repo,
        grouped_candidates,
    )

    ranked_candidates = rank_feature_candidates(
        filtered_candidates,
        feature_name,
    )

    selection = select_ranked_feature_candidate(
        ranked_candidates,
    )

    selected = selection.get(
        "selected"
    )

    if selected:
        selected_branch = selected.get(
            "branch"
        )

        if selected_branch:
            selection["evidence"] = (
                build_feature_evidence(
                    owner,
                    repo,
                    selected_branch,
                )
            )

    selection["feature_name"] = feature_name

    return selection


def get_feature_development_timeline(
    feature_evidence: dict,
) -> dict:
    """Return the best available development timeline."""

    return get_feature_development_timeline_from_evidence(
        feature_evidence
    )


def get_feature_pr_timeline(
    feature_evidence: dict,
) -> dict:
    """Return PR creation, review, and merge evidence."""

    pull_requests = feature_evidence.get(
        "pull_requests",
        [],
    )

    if not pull_requests:
        return {
            "pull_request_count": 0,
            "first_pr_created_at": None,
            "last_pr_updated_at": None,
            "first_merged_at": None,
            "merged_pull_requests": [],
        }

    created_times = [
        pull.get("created_at")
        for pull in pull_requests
        if pull.get("created_at")
    ]

    updated_times = [
        pull.get("updated_at")
        for pull in pull_requests
        if pull.get("updated_at")
    ]

    merged_pull_requests = [
        pull
        for pull in pull_requests
        if pull.get("merged_at")
    ]

    merged_times = [
        pull.get("merged_at")
        for pull in merged_pull_requests
        if pull.get("merged_at")
    ]

    return {
        "pull_request_count": len(
            pull_requests
        ),
        "first_pr_created_at": (
            min(created_times)
            if created_times
            else None
        ),
        "last_pr_updated_at": (
            max(updated_times)
            if updated_times
            else None
        ),
        "first_merged_at": (
            min(merged_times)
            if merged_times
            else None
        ),
        "merged_pull_requests": (
            merged_pull_requests
        ),
    }


def get_feature_merge_status(
    feature_evidence: dict,
) -> dict:
    """Determine whether the feature has a confirmed merged PR."""

    pull_requests = feature_evidence.get(
        "pull_requests",
        [],
    )

    merged_pull_requests = [
        pull
        for pull in pull_requests
        if pull.get("merged_at")
    ]

    if not merged_pull_requests:
        return {
            "merged": False,
            "merge_timestamp": None,
            "merge_commit_sha": None,
            "merged_pull_requests": [],
        }

    merged_pull_requests.sort(
        key=lambda pull: (
            pull.get("merged_at") or ""
        )
    )

    first_merged = merged_pull_requests[0]

    return {
        "merged": True,
        "merge_timestamp": first_merged.get(
            "merged_at"
        ),
        "merge_commit_sha": first_merged.get(
            "merge_commit_sha"
        ),
        "merged_pull_requests": (
            merged_pull_requests
        ),
    }


def build_feature_summary(
    feature_result: dict,
) -> dict:
    """Build a concise feature identification summary."""

    selected = feature_result.get(
        "selected"
    )

    evidence = feature_result.get(
        "evidence",
        {},
    )

    if not selected and not evidence:
        return {
            "status": feature_result.get(
                "match_type"
            ),
            "feature_name": feature_result.get(
                "feature_name"
            ),
            "selected": None,
            "candidate_count": feature_result.get(
                "candidate_count",
                0,
            ),
        }

    branch = (
        selected.get("branch")
        if selected
        else evidence.get(
            "branch",
            {},
        ).get("name")
    )

    development = get_feature_development_timeline(
        evidence
    )

    pr_timeline = get_feature_pr_timeline(
        evidence
    )

    merge_status = get_feature_merge_status(
        evidence
    )

    return {
        "status": feature_result.get(
            "match_type"
        ),
        "feature_name": feature_result.get(
            "feature_name"
        ),
        "branch": branch,
        "base_branch": evidence.get(
            "base_branch"
        ),
        "confidence": (
            selected.get("confidence")
            if selected
            else None
        ),
        "score": (
            selected.get("score")
            if selected
            else None
        ),
        "score_difference": feature_result.get(
            "score_difference"
        ),
        "development": development,
        "pull_requests": pr_timeline,
        "merge": merge_status,
    }

def get_pr_development_timeline(
    owner,
    repo,
    pull_requests,
):
    commits_by_sha = {}

    for pull_request in pull_requests:
        for commit in pull_request.get(
            "pr_commits",
            [],
        ):
            sha = commit.get("sha")

            if not sha:
                continue

            commits_by_sha[sha] = commit

    commits = list(commits_by_sha.values())

    def get_commit_timestamp(commit):
        return (
            commit.get("date")
            or commit.get("committer_date")
        )

    commits.sort(
        key=lambda commit: (
            get_commit_timestamp(commit) or ""
        )
    )

    if not commits:
        return {
            "start_timestamp": None,
            "end_timestamp": None,
            "duration_hours": None,
            "commit_count": 0,
            "first_commit_sha": None,
            "last_commit_sha": None,
        }

    first_commit = commits[0]
    last_commit = commits[-1]

    first_timestamp = get_commit_timestamp(
        first_commit
    )

    last_timestamp = get_commit_timestamp(
        last_commit
    )

    return {
        "start_timestamp": first_timestamp,
        "end_timestamp": last_timestamp,
        "duration_hours": calculate_timestamp_duration(
            first_timestamp,
            last_timestamp,
        ),
        "commit_count": len(commits),
        "first_commit_sha": first_commit.get("sha"),
        "last_commit_sha": last_commit.get("sha"),
    }

def get_feature_development_timeline_from_evidence(feature_evidence):
    branch_exists = feature_evidence.get(
        "branch_exists",
        False,
    )

    if branch_exists:
        development = (
            feature_evidence.get("development")
            or {}
        )

        if development.get("start_timestamp"):
            duration = development.get(
                "development_duration_hours"
            )

            return {
                "start_timestamp":
                    development.get(
                        "start_timestamp"
                    ),
                "end_timestamp":
                    development.get(
                        "end_timestamp"
                    ),
                "duration_hours":
                    duration,
                "commit_count":
                    development.get(
                        "commit_count",
                        0,
                    ),
                "first_commit_sha":
                    development.get(
                        "first_commit_sha"
                    ),
                "last_commit_sha":
                    development.get(
                        "last_commit_sha"
                    ),
                "source": "branch_commits",
            }

    pull_requests = feature_evidence.get(
        "pull_requests",
        [],
    )

    development = get_pr_development_timeline(
        None,
        None,
        pull_requests,
    )

    development["source"] = "pull_request_commits"

    return development


from datetime import datetime


def calculate_timestamp_duration(
    start_timestamp: str | None,
    end_timestamp: str | None,
) -> float | None:
    """Return the duration between two ISO timestamps in hours."""

    if not start_timestamp or not end_timestamp:
        return None

    start = datetime.fromisoformat(
        start_timestamp.replace(
            "Z",
            "+00:00",
        )
    )

    end = datetime.fromisoformat(
        end_timestamp.replace(
            "Z",
            "+00:00",
        )
    )

    duration_seconds = (
        end - start
    ).total_seconds()

    if duration_seconds < 0:
        return None

    return round(
        duration_seconds / 3600,
        2,
    )


def get_pull_request_review_timeline(
    pull_request: dict,
) -> dict:
    """Calculate review and approval timing for a pull request."""

    created_at = pull_request.get(
        "created_at"
    )

    reviews = pull_request.get(
        "reviews",
        [],
    )

    review_timestamps = [
        review.get("submitted_at")
        for review in reviews
        if review.get("submitted_at")
    ]

    review_timestamps.sort()

    approval_timestamps = [
        review.get("submitted_at")
        for review in reviews
        if review.get("state") == "APPROVED"
        and review.get("submitted_at")
    ]

    approval_timestamps.sort()

    first_review_at = (
        review_timestamps[0]
        if review_timestamps
        else None
    )

    first_approval_at = (
        approval_timestamps[0]
        if approval_timestamps
        else None
    )

    merged_at = pull_request.get(
        "merged_at"
    )

    return {
        "pull_number": pull_request.get(
            "number"
        ),
        "created_at": created_at,
        "first_review_at": first_review_at,
        "first_approval_at": first_approval_at,
        "merged_at": merged_at,
        "review_count": pull_request.get(
            "review_count",
            0,
        ),
        "approval_count": pull_request.get(
            "approval_count",
            0,
        ),
        "time_to_first_review_hours": (
            calculate_timestamp_duration(
                created_at,
                first_review_at,
            )
        ),
        "time_to_first_approval_hours": (
            calculate_timestamp_duration(
                created_at,
                first_approval_at,
            )
        ),
        "time_to_merge_hours": (
            calculate_timestamp_duration(
                created_at,
                merged_at,
            )
        ),
    }


def get_feature_review_timeline(
    feature_evidence: dict,
) -> dict:
    """Calculate review-cycle metrics across feature pull requests."""

    pull_requests = feature_evidence.get(
        "pull_requests",
        [],
    )

    timelines = [
        get_pull_request_review_timeline(
            pull_request
        )
        for pull_request in pull_requests
    ]

    review_durations = [
        timeline.get(
            "time_to_first_review_hours"
        )
        for timeline in timelines
        if timeline.get(
            "time_to_first_review_hours"
        ) is not None
    ]

    approval_durations = [
        timeline.get(
            "time_to_first_approval_hours"
        )
        for timeline in timelines
        if timeline.get(
            "time_to_first_approval_hours"
        ) is not None
    ]

    merge_durations = [
        timeline.get(
            "time_to_merge_hours"
        )
        for timeline in timelines
        if timeline.get(
            "time_to_merge_hours"
        ) is not None
    ]

    return {
        "pull_request_count": len(
            timelines
        ),
        "reviewed_pull_request_count": len(
            review_durations
        ),
        "approved_pull_request_count": len(
            approval_durations
        ),
        "merged_pull_request_count": len(
            merge_durations
        ),
        "pull_requests": timelines,
        "average_time_to_first_review_hours": (
            round(
                sum(review_durations)
                / len(review_durations),
                2,
            )
            if review_durations
            else None
        ),
        "average_time_to_first_approval_hours": (
            round(
                sum(approval_durations)
                / len(approval_durations),
                2,
            )
            if approval_durations
            else None
        ),
        "average_time_to_merge_hours": (
            round(
                sum(merge_durations)
                / len(merge_durations),
                2,
            )
            if merge_durations
            else None
        ),
    }