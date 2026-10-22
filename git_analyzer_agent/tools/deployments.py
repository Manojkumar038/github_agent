from tools.github_client import github_get


from tools.github_client import github_get


def get_github_deployments(
    owner: str,
    repo: str,
) -> dict:
    """Return GitHub deployments with their latest status."""

    deployments = github_get(
        f"/repos/{owner}/{repo}/deployments"
        "?per_page=100"
    )

    results = []

    for deployment in deployments:
        deployment_id = deployment.get("id")

        statuses = github_get(
            f"/repos/{owner}/{repo}/deployments/"
            f"{deployment_id}/statuses?per_page=100"
        )

        status_items = statuses if isinstance(statuses, list) else []

        latest_status = (
            status_items[0]
            if status_items
            else None
        )

        results.append(
            {
                "id": deployment_id,
                "environment": deployment.get("environment"),
                "description": deployment.get("description"),
                "ref": deployment.get("ref"),
                "sha": deployment.get("sha"),
                "created_at": deployment.get("created_at"),
                "updated_at": deployment.get("updated_at"),
                "latest_status": (
                    latest_status.get("state")
                    if latest_status
                    else None
                ),
                "status_created_at": (
                    latest_status.get("created_at")
                    if latest_status
                    else None
                ),
                "environment_url": (
                    latest_status.get("environment_url")
                    if latest_status
                    else None
                ),
                "url": deployment.get("url"),
                "statuses_url": deployment.get("statuses_url"),
            }
        )

    return {
        "deployment_count": len(results),
        "deployments": results,
    }

def get_github_deployment_statuses(
    owner: str,
    repo: str,
    deployment_id: int,
) -> dict:
    """Return statuses associated with a GitHub deployment."""

    statuses = github_get(
        f"/repos/{owner}/{repo}/deployments/{deployment_id}/statuses"
        "?per_page=100"
    )

    results = [
        {
            "id": status.get("id"),
            "state": status.get("state"),
            "environment": status.get("environment"),
            "environment_url": status.get("environment_url"),
            "description": status.get("description"),
            "created_at": status.get("created_at"),
            "updated_at": status.get("updated_at"),
            "url": status.get("target_url"),
        }
        for status in statuses
    ]

    return {
        "deployment_id": deployment_id,
        "status_count": len(results),
        "statuses": results,
    }