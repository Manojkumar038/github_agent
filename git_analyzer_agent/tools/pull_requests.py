from tools.github_client import github_get


def get_github_pull_requests(
    owner: str,
    repo: str,
    state: str = "all",
) -> dict:
    """Return pull requests with lifecycle information."""

    pulls = github_get(
        f"/repos/{owner}/{repo}/pulls"
        f"?state={state}&per_page=100"
    )

    results = []

    for pull in pulls:
        results.append(
            {
                "number": pull.get("number"),
                "title": pull.get("title"),
                "state": pull.get("state"),
                "draft": pull.get("draft"),
                "created_at": pull.get("created_at"),
                "updated_at": pull.get("updated_at"),
                "closed_at": pull.get("closed_at"),
                "merged_at": pull.get("merged_at"),
                "merge_commit_sha": pull.get("merge_commit_sha"),
                "source_branch": (
                    pull.get("head", {}).get("ref")
                ),
                "source_sha": (
                    pull.get("head", {}).get("sha")
                ),
                "target_branch": (
                    pull.get("base", {}).get("ref")
                ),
                "target_sha": (
                    pull.get("base", {}).get("sha")
                ),
                "author": (
                    pull.get("user", {}).get("login")
                ),
                "url": pull.get("html_url"),
            }
        )

    return {
        "pull_request_count": len(results),
        "pull_requests": results,
    }

def get_github_pull_request_reviews(
    owner: str,
    repo: str,
    pull_number: int,
) -> dict:
    """Return reviews and approval information for a pull request."""

    reviews = []
    page = 1
    while True:
        page_reviews = github_get(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
            f"?per_page=100&page={page}"
        )
        if not isinstance(page_reviews, list) or not page_reviews:
            break
        reviews.extend(page_reviews)
        if len(page_reviews) < 100:
            break
        page += 1

    results = [
        {
            "id": review.get("id"),
            "user": (
                review.get("user", {}).get("login")
            ),
            "state": review.get("state"),
            "submitted_at": review.get("submitted_at"),
            "commit_id": review.get("commit_id"),
            "url": review.get("html_url"),
        }
        for review in reviews
    ]

    approvals = [
        review
        for review in results
        if review.get("state") == "APPROVED"
    ]

    return {
        "pull_number": pull_number,
        "review_count": len(results),
        "approval_count": len(approvals),
        "reviews": results,
    }

def get_github_pull_request_commits(
    owner: str,
    repo: str,
    pull_number: int,
) -> dict:
    """Return commits associated with a pull request."""

    commits = []
    page = 1
    while True:
        page_commits = github_get(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/commits"
            f"?per_page=100&page={page}"
        )
        if not isinstance(page_commits, list) or not page_commits:
            break
        commits.extend(page_commits)
        if len(page_commits) < 100:
            break
        page += 1

    results = [
        {
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
            "parents": [
                parent.get("sha")
                for parent in commit.get("parents", [])
            ],
            "url": commit.get("html_url"),
        }
        for commit in commits
    ]

    return {
        "pull_number": pull_number,
        "commit_count": len(results),
        "commits": results,
    }

def get_github_pull_requests_for_branch(
    owner: str,
    repo: str,
    branch: str,
) -> dict:
    """Return pull requests associated with a source branch."""

    pull_data = get_github_pull_requests(
        owner,
        repo,
        state="all",
    )

    matching_prs = [
        pull
        for pull in pull_data.get("pull_requests", [])
        if pull.get("source_branch") == branch
    ]

    return {
        "branch": branch,
        "pull_request_count": len(matching_prs),
        "pull_requests": matching_prs,
    }


def get_github_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
) -> dict:
    """Return detailed information about a single pull request."""

    pull = github_get(
        f"/repos/{owner}/{repo}/pulls/{pull_number}"
    )

    return {
        "number": pull.get("number"),
        "title": pull.get("title"),
        "body": pull.get("body"),
        "state": pull.get("state"),
        "draft": pull.get("draft"),
        "created_at": pull.get("created_at"),
        "updated_at": pull.get("updated_at"),
        "closed_at": pull.get("closed_at"),
        "merged_at": pull.get("merged_at"),
        "merge_commit_sha": pull.get("merge_commit_sha"),
        "source_branch": (
            pull.get("head", {}).get("ref")
        ),
        "source_sha": (
            pull.get("head", {}).get("sha")
        ),
        "target_branch": (
            pull.get("base", {}).get("ref")
        ),
        "target_sha": (
            pull.get("base", {}).get("sha")
        ),
        "author": (
            pull.get("user", {}).get("login")
        ),
        "url": pull.get("html_url"),
    }