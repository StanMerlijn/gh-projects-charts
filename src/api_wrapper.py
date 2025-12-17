"""
@file api_wrapper.py
@brief Lightweight GitHub GraphQL API wrapper.
@details This module encapsulates loading a GraphQL query from disk and executing it
against the GitHub GraphQL endpoint using a personal access token provided via
environment (dotenv).
@author gh-projects-charts maintainers
@date 2025-11-05
"""

import requests
from dotenv import dotenv_values

from util import load_file

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

        cursor = None
        all_data = None
        while True:
            variables = {
                "login": self.config["user_name"],
                "number": self.config["project_number"],
                "max_items": self.config["max_items"],
                "cursor": cursor,
            }
            resp = requests.post(
                API_URL,
                json={"query": self.query, "variables": variables},
                headers=self.headers,
            )
            data = resp.json()

            items = data["data"]["user"]["projectV2"]["items"]

            if all_data is None:
                all_data = data
            else:
                all_data["data"]["user"]["projectV2"]["items"]["nodes"].extend(
                    items["nodes"]
                )

            page_info = items["pageInfo"]
            next_cursor = page_info["endCursor"]

            
            if not page_info["hasNextPage"]:
                break

            if next_cursor is None or next_cursor == cursor:
                # safety break to avoid infinite loops
                break
            
            cursor = next_cursor
            
            
        print(len(all_data["data"]["user"]["projectV2"]["items"]["nodes"]))
        return all_data
