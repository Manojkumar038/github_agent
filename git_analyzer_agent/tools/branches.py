from tools.github_client import github_get


def get_github_branches(owner: str, repo: str) -> dict:
    """Return branches available in a GitHub repository."""

    branches = github_get(
        f"/repos/{owner}/{repo}/branches?per_page=100"
    )

    results = []

    for branch in branches:
        commit = branch.get("commit") or {}

        results.append(
            {
                "name": branch.get("name"),
                "protected": branch.get("protected"),
                "sha": commit.get("sha"),
                "commit_url": commit.get("url"),
            }
        )

    return {
        "branch_count": len(results),
        "branches": results,
    }

def get_github_branch(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Return detailed information about a specific branch."""

    branch_data = github_get(
        f"/repos/{owner}/{repo}/branches/{branch}"
    )

    commit = branch_data.get("commit") or {}

    return {
        "name": branch_data.get("name"),
        "protected": branch_data.get("protected"),
        "sha": commit.get("sha"),
        "commit_url": commit.get("url"),
    }

from tools.commits import (
    get_github_commits,
    get_meaningful_commits,
)



def get_github_branch_meaningful_commits(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Return meaningful commits associated with a branch."""

    from tools.commits import get_github_commit_details

    commit_data = get_github_commits(
        owner,
        repo,
        branch,
    )

    detailed_commits = []

    for commit in commit_data.get("commits", []):
        sha = commit.get("sha")

        if not sha:
            continue

        details = get_github_commit_details(
            owner,
            repo,
            sha,
        )

        detailed_commits.append(details)

    meaningful_commits = get_meaningful_commits(
        detailed_commits
    )

    return {
        "branch": branch,
        "commit_count": len(meaningful_commits),
        "commits": meaningful_commits,
    }