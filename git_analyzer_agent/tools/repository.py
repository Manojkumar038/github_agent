from tools.github_client import github_get


def get_github_repo_info(owner: str, repo: str) -> dict:
    """Return basic repository metadata and languages."""
    repository = github_get(f"/repos/{owner}/{repo}")
    languages = github_get(f"/repos/{owner}/{repo}/languages")

    return {
        "full_name": repository.get("full_name"),
        "description": repository.get("description"),
        "default_branch": repository.get("default_branch"),
        "visibility": repository.get("visibility"),
        "is_fork": repository.get("fork"),
        "stars": repository.get("stargazers_count"),
        "forks": repository.get("forks_count"),
        "open_issues": repository.get("open_issues_count"),
        "languages": languages,
        "url": repository.get("html_url"),
    }

def get_github_contributors(
    owner: str,
    repo: str,
) -> dict:
    """Return repository contributors."""

    contributors = github_get(
        f"/repos/{owner}/{repo}/contributors"
        "?per_page=100"
    )

    results = [
        {
            "login": contributor.get("login"),
            "contributions": contributor.get("contributions"),
            "type": contributor.get("type"),
            "url": contributor.get("html_url"),
        }
        for contributor in contributors
    ]

    return {
        "contributor_count": len(results),
        "contributors": results,
    }

def get_github_events(
    owner: str,
    repo: str,
) -> dict:
    """Return recent repository events."""

    events = github_get(
        f"/repos/{owner}/{repo}/events"
    )

    results = [
        {
            "id": event.get("id"),
            "type": event.get("type"),
            "created_at": event.get("created_at"),
            "actor": (
                event.get("actor", {}).get("login")
                if event.get("actor")
                else None
            ),
            "payload": event.get("payload"),
        }
        for event in events
    ]

    return {
        "event_count": len(results),
        "events": results,
    }