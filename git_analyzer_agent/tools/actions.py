from tools.github_client import github_get


def get_github_actions_info(owner: str, repo: str) -> dict:
    """Return whether a GitHub repository has Actions workflows and list them."""
    workflows = github_get(
        f"/repos/{owner}/{repo}/actions/workflows"
    )

    workflow_items = workflows.get("workflows", [])

    return {
        "has_actions": bool(workflow_items),
        "workflow_count": workflows.get(
            "total_count",
            len(workflow_items),
        ),
        "workflows": [
            {
                "name": workflow.get("name"),
                "state": workflow.get("state"),
                "path": workflow.get("path"),
                "url": workflow.get("html_url"),
            }
            for workflow in workflow_items
        ],
    }

def get_github_actions_runs(
    owner: str,
    repo: str,
    workflow_id: str | int | None = None,
) -> dict:
    """Return GitHub Actions workflow runs."""

    if workflow_id:
        endpoint = (
            f"/repos/{owner}/{repo}/actions/workflows/"
            f"{workflow_id}/runs?per_page=100"
        )
    else:
        endpoint = (
            f"/repos/{owner}/{repo}/actions/runs"
            "?per_page=100"
        )

    response = github_get(endpoint)

    runs = response.get("workflow_runs", [])

    results = [
        {
            "id": run.get("id"),
            "name": run.get("name"),
            "workflow_id": run.get("workflow_id"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "event": run.get("event"),
            "branch": run.get("head_branch"),
            "commit_sha": run.get("head_sha"),
            "created_at": run.get("created_at"),
            "started_at": run.get("run_started_at"),
            "updated_at": run.get("updated_at"),
            "url": run.get("html_url"),
        }
        for run in runs
    ]

    return {
        "run_count": len(results),
        "runs": results,
    }

def get_github_actions_jobs(
    owner: str,
    repo: str,
    run_id: int,
) -> dict:
    """Return jobs associated with a GitHub Actions workflow run."""

    response = github_get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        "?per_page=100"
    )

    jobs = response.get("jobs", [])

    results = [
        {
            "id": job.get("id"),
            "name": job.get("name"),
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "url": job.get("html_url"),
        }
        for job in jobs
    ]

    return {
        "run_id": run_id,
        "job_count": len(results),
        "jobs": results,
    }

def get_github_actions_job_details(
    owner: str,
    repo: str,
    job_id: int,
) -> dict:
    """Return detailed information about a GitHub Actions job."""

    job = github_get(
        f"/repos/{owner}/{repo}/actions/jobs/{job_id}"
    )

    steps = [
        {
            "name": step.get("name"),
            "status": step.get("status"),
            "conclusion": step.get("conclusion"),
            "started_at": step.get("started_at"),
            "completed_at": step.get("completed_at"),
            "number": step.get("number"),
        }
        for step in job.get("steps", [])
    ]

    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "status": job.get("status"),
        "conclusion": job.get("conclusion"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "steps": steps,
        "url": job.get("html_url"),
    }