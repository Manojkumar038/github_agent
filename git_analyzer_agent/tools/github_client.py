import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_API_URL = "https://api.github.com"
GITHUB_API_URL = "https://api.github.com"


def github_get(endpoint: str) -> dict:
    """Get a JSON response from GitHub's REST API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "git-analyzer-agent",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        f"{GITHUB_API_URL}{endpoint}",
        headers=headers,
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        if error.code == 404:
            raise ValueError(
                "GitHub repository or endpoint was not found."
            ) from error

        if error.code == 403:
            raise ValueError(
                "GitHub API access was denied or rate-limited. "
                "Set GITHUB_TOKEN for higher limits."
            ) from error

        raise ValueError(
            f"GitHub API request failed with status {error.code}."
        ) from error

    except URLError as error:
        raise ValueError(
            f"Could not reach GitHub: {error.reason}."
        ) from error