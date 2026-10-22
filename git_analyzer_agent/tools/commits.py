from tools.github_client import github_get


def get_github_commits(
    owner: str,
    repo: str,
    branch: str | None = None,
) -> dict:
    """Return commits with metadata and changed-file information."""

    endpoint = f"/repos/{owner}/{repo}/commits?per_page=100"

    if branch:
        endpoint += f"&sha={branch}"

    commits = github_get(endpoint)

    results = []

    for commit in commits:
        sha = commit.get("sha")

        results.append(
            {
                "sha": sha,
                "message": (
                    commit.get("commit", {})
                    .get("message")
                ),
                "author": (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("name")
                ),
                "author_email": (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("email")
                ),
                "date": (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("date")
                ),
                "committer_date": (
                    commit.get("commit", {})
                    .get("committer", {})
                    .get("date")
                ),
                "url": commit.get("html_url"),
                "parents": [
                    parent.get("sha")
                    for parent in commit.get("parents", [])
                ],
                "changed_files": [],
            }
        )

    return {
        "commit_count": len(results),
        "commits": results,
    }

def get_github_commit_details(
    owner: str,
    repo: str,
    sha: str,
) -> dict:
    """Return detailed information about a commit, including changed files."""

    commit = github_get(
        f"/repos/{owner}/{repo}/commits/{sha}"
    )

    files = commit.get("files", [])

    changed_files = [
        {
            "filename": file.get("filename"),
            "status": file.get("status"),
            "additions": file.get("additions"),
            "deletions": file.get("deletions"),
            "changes": file.get("changes"),
            "patch": file.get("patch"),
        }
        for file in files
    ]

    return {
        "sha": commit.get("sha"),
        "message": (
            commit.get("commit", {})
            .get("message")
        ),
        "author": (
            commit.get("commit", {})
            .get("author", {})
            .get("name")
        ),
        "date": (
            commit.get("commit", {})
            .get("author", {})
            .get("date")
        ),
        "parents": [
            parent.get("sha")
            for parent in commit.get("parents", [])
        ],
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "url": commit.get("html_url"),
    }

def get_github_branch_commit_details(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Return detailed commit information for a branch."""

    commits_response = get_github_commits(
        owner,
        repo,
        branch,
    )

    detailed_commits = []

    for commit in commits_response.get("commits", []):
        sha = commit.get("sha")

        if not sha:
            continue

        details = get_github_commit_details(
            owner,
            repo,
            sha,
        )

        detailed_commits.append(details)

    return {
        "branch": branch,
        "commit_count": len(detailed_commits),
        "commits": detailed_commits,
    }

def get_github_commit_activity(
    owner: str,
    repo: str,
) -> dict:
    """Return repository commit activity."""

    activity = github_get(
        f"/repos/{owner}/{repo}/stats/commit_activity"
    )

    if not isinstance(activity, list):
        return {
            "week_count": 0,
            "activity": [],
        }

    results = [
        {
            "week": item.get("week"),
            "total": item.get("total"),
            "days": item.get("days"),
        }
        for item in activity
    ]

    return {
        "week_count": len(results),
        "activity": results,
    }


def get_github_commit_contributors(
    owner: str,
    repo: str,
) -> dict:
    """Return commit contribution statistics for repository contributors."""

    stats = github_get(
        f"/repos/{owner}/{repo}/stats/contributors"
    )

    if not isinstance(stats, list):
        return {
            "contributor_count": 0,
            "contributors": [],
        }

    results = [
        {
            "login": (
                contributor.get("author", {}).get("login")
                if contributor.get("author")
                else None
            ),
            "total_commits": contributor.get("total"),
            "weeks": contributor.get("weeks", []),
        }
        for contributor in stats
    ]

    return {
        "contributor_count": len(results),
        "contributors": results,
    }

def compare_github_commits(
    owner: str,
    repo: str,
    base: str,
    head: str,
) -> dict:
    """Compare two commits and return changed files and commit statistics."""

    comparison = github_get(
        f"/repos/{owner}/{repo}/compare/{base}...{head}"
    )

    files = comparison.get("files", [])

    changed_files = [
        {
            "filename": file.get("filename"),
            "status": file.get("status"),
            "additions": file.get("additions"),
            "deletions": file.get("deletions"),
            "changes": file.get("changes"),
        }
        for file in files
    ]

    return {
        "base": base,
        "head": head,
        "status": comparison.get("status"),
        "ahead_by": comparison.get("ahead_by"),
        "behind_by": comparison.get("behind_by"),
        "total_commits": comparison.get("total_commits"),
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "commits": [
            {
                "sha": commit.get("sha"),
                "message": (
                    commit.get("commit", {})
                    .get("message")
                ),
                "date": (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("date")
                ),
            }
            for commit in comparison.get("commits", [])
        ],
        "url": comparison.get("html_url"),
    }

def get_commit_timestamp(commit: dict) -> str | None:
    """Return the preferred timestamp for a commit."""

    return (
        commit.get("committer_date")
        or commit.get("date")
    )


def is_meaningful_commit(commit: dict) -> bool:
    """Return whether a commit is suitable for feature timeline analysis."""

    message = (commit.get("message") or "").strip()

    if not message:
        return False

    normalized_message = message.lower()

    ignored_prefixes = (
        "merge ",
        "merge pull request",
        "merge branch",
        "merge remote-tracking branch",
    )

    if normalized_message.startswith(ignored_prefixes):
        return False

    return True

def is_meaningful_commit(commit: dict) -> bool:
    """Return whether a commit is suitable for feature timeline analysis."""

    message = (commit.get("message") or "").strip()

    if not message:
        return False

    normalized_message = message.lower()

    ignored_prefixes = (
        "merge ",
        "merge pull request",
        "merge branch",
        "merge remote-tracking branch",
    )

    if normalized_message.startswith(ignored_prefixes):
        return False

    changed_files = commit.get("changed_files")

    if changed_files is not None and not changed_files:
        return False

    return True


from datetime import datetime


def calculate_commit_duration(
    start_timestamp: str | None,
    end_timestamp: str | None,
) -> float | None:
    """Return the duration between two GitHub timestamps in hours."""

    if not start_timestamp or not end_timestamp:
        return None

    start = datetime.fromisoformat(
        start_timestamp.replace("Z", "+00:00")
    )

    end = datetime.fromisoformat(
        end_timestamp.replace("Z", "+00:00")
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


def calculate_commit_range_duration(
    commits: list[dict],
) -> float | None:
    """Return the duration between the first and last meaningful commits."""

    meaningful_commits = [
        commit
        for commit in commits
        if is_meaningful_commit(commit)
    ]

    timestamps = [
        get_commit_timestamp(commit)
        for commit in meaningful_commits
    ]

    timestamps = [
        timestamp
        for timestamp in timestamps
        if timestamp
    ]

    if len(timestamps) < 2:
        return None

    timestamps.sort()

    return calculate_commit_duration(
        timestamps[0],
        timestamps[-1],
    )

def get_first_meaningful_commit(
    commits: list[dict],
) -> dict | None:
    """Return the earliest meaningful commit."""

    meaningful_commits = [
        commit
        for commit in commits
        if is_meaningful_commit(commit)
    ]

    if not meaningful_commits:
        return None

    meaningful_commits.sort(
        key=lambda commit: (
            get_commit_timestamp(commit) or ""
        )
    )

    return meaningful_commits[0]


def get_last_meaningful_commit(
    commits: list[dict],
) -> dict | None:
    """Return the latest meaningful commit."""

    meaningful_commits = [
        commit
        for commit in commits
        if is_meaningful_commit(commit)
    ]

    if not meaningful_commits:
        return None

    meaningful_commits.sort(
        key=lambda commit: (
            get_commit_timestamp(commit) or ""
        )
    )

    return meaningful_commits[-1]

def get_meaningful_commits(
    commits: list[dict],
) -> list[dict]:
    """Return meaningful commits sorted chronologically."""

    meaningful_commits = [
        commit
        for commit in commits
        if is_meaningful_commit(commit)
    ]

    meaningful_commits.sort(
        key=lambda commit: (
            get_commit_timestamp(commit) or ""
        )
    )

    return meaningful_commits

def get_unique_commit_shas(
    commits: list[dict],
    base_commit_shas: set[str],
) -> list[dict]:
    """Return commits that are not already present in the base history."""

    return [
        commit
        for commit in commits
        if commit.get("sha") not in base_commit_shas
    ]

def get_commit_sha_set(
    commits: list[dict],
) -> set[str]:
    """Return the set of commit SHAs from a commit collection."""

    return {
        commit.get("sha")
        for commit in commits
        if commit.get("sha")
    }

def get_branch_unique_commits(
    owner: str,
    repo: str,
    branch_commits: list[dict],
    base_branch_commits: list[dict],
) -> list[dict]:
    """Return commits that are unique to a branch."""

    base_commit_shas = get_commit_sha_set(
        base_branch_commits
    )

    return get_unique_commit_shas(
        branch_commits,
        base_commit_shas,
    )

def get_github_branch_unique_commits(
    owner: str,
    repo: str,
    branch: str,
    base_branch: str,
) -> dict:
    """Return commits unique to a branch compared with a base branch."""

    branch_data = get_github_commits(
        owner,
        repo,
        branch,
    )

    base_data = get_github_commits(
        owner,
        repo,
        base_branch,
    )

    unique_commits = get_branch_unique_commits(
        owner,
        repo,
        branch_data.get("commits", []),
        base_data.get("commits", []),
    )

    return {
        "branch": branch,
        "base_branch": base_branch,
        "commit_count": len(unique_commits),
        "commits": unique_commits,
    }


def get_github_branch_unique_commit_details(
    owner: str,
    repo: str,
    branch: str,
    base_branch: str,
) -> dict:
    """Return detailed commits unique to a branch."""

    unique_data = get_github_branch_unique_commits(
        owner,
        repo,
        branch,
        base_branch,
    )

    detailed_commits = []

    for commit in unique_data.get("commits", []):
        sha = commit.get("sha")

        if not sha:
            continue

        detailed_commits.append(
            get_github_commit_details(
                owner,
                repo,
                sha,
            )
        )

    return {
        "branch": branch,
        "base_branch": base_branch,
        "commit_count": len(detailed_commits),
        "commits": detailed_commits,
    }

def calculate_branch_development_duration(
    commits: list[dict],
) -> float | None:
    """Return development duration for branch-specific meaningful commits."""

    meaningful_commits = get_meaningful_commits(
        commits
    )

    if len(meaningful_commits) < 2:
        return 0.0 if meaningful_commits else None

    return calculate_commit_range_duration(
        meaningful_commits
    )

def get_branch_development_timeline(
    commits: list[dict],
) -> dict:
    """Return the development timeline for meaningful branch commits."""

    meaningful_commits = get_meaningful_commits(
        commits
    )

    if not meaningful_commits:
        return {
            "first_commit": None,
            "last_commit": None,
            "start_timestamp": None,
            "end_timestamp": None,
            "duration_hours": None,
        }

    first_commit = meaningful_commits[0]
    last_commit = meaningful_commits[-1]

    start_timestamp = get_commit_timestamp(
        first_commit
    )
    end_timestamp = get_commit_timestamp(
        last_commit
    )

    return {
        "first_commit": first_commit,
        "last_commit": last_commit,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "duration_hours": calculate_branch_development_duration(
            meaningful_commits
        ),
    }


def analyze_github_branch_development(
    owner: str,
    repo: str,
    branch: str,
    base_branch: str,
) -> dict:
    """Analyze development activity unique to a branch."""

    unique_data = get_github_branch_unique_commit_details(
        owner,
        repo,
        branch,
        base_branch,
    )

    commits = unique_data.get(
        "commits",
        [],
    )

    timeline = get_branch_development_timeline(
        commits
    )

    return {
        "branch": branch,
        "base_branch": base_branch,
        "commit_count": len(commits),
        "commits": commits,
        "development": timeline,
    }

def get_branch_development_summary(
    owner: str,
    repo: str,
    branch: str,
    base_branch: str,
) -> dict:
    """Return a concise development summary for a branch."""

    analysis = analyze_github_branch_development(
        owner,
        repo,
        branch,
        base_branch,
    )

    development = analysis.get(
        "development",
        {},
    )

    return {
        "branch": analysis.get("branch"),
        "base_branch": analysis.get("base_branch"),
        "commit_count": analysis.get("commit_count"),
        "start_timestamp": development.get(
            "start_timestamp"
        ),
        "end_timestamp": development.get(
            "end_timestamp"
        ),
        "development_duration_hours": development.get(
            "duration_hours"
        ),
        "first_commit_sha": (
            development.get("first_commit", {})
            .get("sha")
            if development.get("first_commit")
            else None
        ),
        "last_commit_sha": (
            development.get("last_commit", {})
            .get("sha")
            if development.get("last_commit")
            else None
        ),
    }