"""Lightweight GitHub GraphQL API wrapper.

This module encapsulates loading a GraphQL query from disk and executing it
against the GitHub GraphQL endpoint using a personal access token provided via
environment (dotenv)."""

from dotenv import dotenv_values
from util import load_file
import requests

env = dotenv_values()
API_URL = "https://api.github.com/graphql"


class ApiWrapper:
    """Simple wrapper to perform authenticated GraphQL requests to GitHub.

    Attributes:
        config: Runtime configuration loaded from `config.json`.
        query: GraphQL query loaded from `query.graphql`.
        headers: HTTP headers including the Authorization bearer token.
    """

    def __init__(self, config: dict, working_path: str) -> None:
        """Initialize the API wrapper with configuration and query path.

        Args:
            config: Configuration dictionary with keys like "user_name",
                "project_number", and "max_items".
            working_path: Directory that contains the `query.graphql` file.
        """
        self.config = config
        self.query = load_file(working_path / "query.graphql")
        self.headers = {"Authorization": f"Bearer {env['GITHUB_TOKEN']}"}

    def get_request(self) -> dict:
        """Execute the GraphQL query and return the JSON response.

        Builds the variables payload from `self.config` and performs a POST
        request to the GitHub GraphQL API.

        Returns:
            The parsed JSON response as a dictionary.
        """
        variables = {
            "login": self.config["user_name"],
            "number": self.config["project_number"],
            "max_items": self.config["max_items"],
        }
        resp = requests.post(
            API_URL,
            json={"query": self.query, "variables": variables},
            headers=self.headers,
        )
        data = resp.json()

        return data
