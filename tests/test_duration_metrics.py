import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from git_analyzer_agent.analysis.repository_data_extractor import (
    _build_environment_summary,
    _deployment_matches_feature_branch,
    _summarize_branch_human_commits,
    calculate_pull_request_lifecycle,
    days_between,
)
from git_analyzer_agent.github_report_generator import hours_to_days


def test_hours_to_days_round_trip():
    assert hours_to_days(24) == 1.0
    assert hours_to_days(48.5) == 2.02
    assert hours_to_days(None) is None


def test_days_between_uses_hours_conversion():
    assert days_between("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z") == 2.0
    assert days_between("2026-01-01T00:00:00Z", "2026-01-01T12:00:00Z") == 0.5


def test_environment_summary_detects_dev_test_prod_from_repo_deployments():
    deployments = [
        {"environment": "Prod", "status": "success", "status_created_at": "2026-10-06T13:32:20Z"},
        {"environment": "Test", "status": "success", "status_created_at": "2026-10-06T00:43:45Z"},
        {"environment": "Dev", "status": "success", "status_created_at": "2026-10-05T12:00:00Z"},
    ]

    summary = _build_environment_summary(deployments)

    assert summary["dev_deployed_at"] == "2026-10-05T12:00:00Z"
    assert summary["test_deployed_at"] == "2026-10-06T00:43:45Z"
    assert summary["prod_deployed_at"] == "2026-10-06T13:32:20Z"


def test_feature_deployment_matching_requires_branch_or_related_sha():
    related_shas = {"feature-tip", "pr-merge"}

    assert _deployment_matches_feature_branch(
        {"ref": "feature/login", "sha": "other"},
        "feature/login",
        related_shas,
    )
    assert _deployment_matches_feature_branch(
        {"ref": "main", "sha": "pr-merge"},
        "feature/login",
        related_shas,
    )
    assert not _deployment_matches_feature_branch(
        {"ref": "main", "sha": "unrelated"},
        "feature/login",
        related_shas,
    )


def test_developer_activity_reports_commit_window_not_feature_window():
    commits = [
        {
            "author": {"login": "alice"},
            "commit": {"author": {"date": "2026-01-01T09:00:00Z"}},
        },
        {
            "author": {"login": "alice"},
            "commit": {"author": {"date": "2026-01-02T09:00:00Z"}},
        },
        {
            "author": {"login": "bob"},
            "commit": {"author": {"date": "2026-01-02T12:00:00Z"}},
        },
    ]

    summary = _summarize_branch_human_commits(commits)
    activity = {item["developer"]: item for item in summary["developer_activity"]}

    assert activity["alice"]["human_commit_count"] == 2
    assert activity["alice"]["activity_span_hours"] == 24.0
    assert activity["alice"]["activity_span_days"] == 1.0
    assert activity["bob"]["human_commit_count"] == 1
    assert activity["bob"]["activity_span_hours"] == 0.0


def test_pull_request_lifecycle_calculates_review_and_merge_intervals():
    lifecycle = calculate_pull_request_lifecycle(
        {
            "created_at": "2026-10-01T00:00:00Z",
            "merged_at": "2026-10-03T02:00:00Z",
        },
        [
            {"state": "CHANGES_REQUESTED", "submitted_at": "2026-10-02T00:00:00Z"},
            {"state": "APPROVED", "submitted_at": "2026-10-02T12:00:00Z"},
        ],
    )

    assert lifecycle["created_to_first_review_hours"] == 24.0
    assert lifecycle["first_review_to_approval_hours"] == 12.0
    assert lifecycle["approval_to_merge_hours"] == 14.0
    assert lifecycle["created_to_merge_hours"] == 50.0
    assert lifecycle["changes_requested_count"] == 1


def test_pull_request_lifecycle_leaves_unavailable_timings_none():
    lifecycle = calculate_pull_request_lifecycle(
        {"created_at": "2026-10-01T00:00:00Z", "merged_at": None},
        [],
    )

    assert lifecycle["created_to_first_review_hours"] is None
    assert lifecycle["approval_to_merge_hours"] is None
    assert lifecycle["created_to_merge_hours"] is None
