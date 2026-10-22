from tools.github_client import github_get


def get_github_releases(
    owner: str,
    repo: str,
) -> dict:
    """Return releases published for a GitHub repository."""

    releases = github_get(
        f"/repos/{owner}/{repo}/releases"
        "?per_page=100"
    )

    results = [
        {
            "id": release.get("id"),
            "name": release.get("name"),
            "tag_name": release.get("tag_name"),
            "target_commitish": release.get("target_commitish"),
            "draft": release.get("draft"),
            "prerelease": release.get("prerelease"),
            "created_at": release.get("created_at"),
            "published_at": release.get("published_at"),
            "url": release.get("html_url"),
        }
        for release in releases
    ]

    return {
        "release_count": len(results),
        "releases": results,
    }

def get_github_tags(
    owner: str,
    repo: str,
) -> dict:
    """Return Git tags for a GitHub repository."""

    tags = github_get(
        f"/repos/{owner}/{repo}/tags"
        "?per_page=100"
    )

    results = [
        {
            "name": tag.get("name"),
            "sha": (
                tag.get("commit", {}).get("sha")
                if tag.get("commit")
                else None
            ),
        }
        for tag in tags
    ]

    return {
        "tag_count": len(results),
        "tags": results,
    }


def get_github_release_by_tag(
    owner: str,
    repo: str,
    tag_name: str,
) -> dict:
    """Return release information for a specific tag."""

    release = github_get(
        f"/repos/{owner}/{repo}/releases/tags/{tag_name}"
    )

    return {
        "id": release.get("id"),
        "name": release.get("name"),
        "tag_name": release.get("tag_name"),
        "target_commitish": release.get("target_commitish"),
        "draft": release.get("draft"),
        "prerelease": release.get("prerelease"),
        "created_at": release.get("created_at"),
        "published_at": release.get("published_at"),
        "url": release.get("html_url"),
    }