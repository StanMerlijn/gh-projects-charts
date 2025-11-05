"""
@file main.py
@brief Orchestrate fetching GitHub Projects data and plotting charts.
@details Loads config, fetches/caches GraphQL data, filters issues, and delegates plotting to `BurndownChart`.
@dependencies requests, python-dotenv, matplotlib
@author gh-projects-charts maintainers
@date 2025-11-05
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from pprint import pprint
from typing import Optional

from api_wrapper import ApiWrapper
from burndown_chart import BurndownChart
from util import utc_to_date

FILE_PATH = Path(__file__).parent.resolve()
RESOURCES_PATH = FILE_PATH / "resources"


class dataGenerator:
    """Drive data collection, transformation, and chart rendering."""

    def __init__(self) -> None:
        """Load configuration, compute date range, and initialize API client."""
        self.config = self.get_config()
        self.sprint_dates = self.__create_dates()
        self.date_keys = ["closedAt", "createdAt"]
        self.api_wrapper = ApiWrapper(self.config, RESOURCES_PATH)

        self.start_date: datetime = datetime.strptime(
            self.config["sprint_data"]["start_date"], "%d-%m-%Y"
        ).date()
        self.end_date: datetime = datetime.strptime(
            self.config["sprint_data"]["end_date"], "%d-%m-%Y"
        ).date()

        self.burndown_chart = BurndownChart(
            self.config, self.sprint_dates, self.start_date, self.end_date
        )

    def __check_and_get_cache(
        self, ttl_seconds: int = 3600, force_refresh: bool = False
    ) -> Optional[dict]:
        """Return cached API response from data.json when fresh; otherwise None.

        Args:
            ttl_seconds: Consider cache valid if modified within this many seconds.
                         Set to 0 or a negative value to always use cache when present.
            force_refresh: If True, bypass cache and return None.

        Returns:
            Parsed JSON dict if valid cache is found; otherwise None.
        """
        if force_refresh:
            return None

        cache_path = RESOURCES_PATH / "data.json"
        if not cache_path.exists():
            return None

        try:
            if ttl_seconds > 0:
                mtime = cache_path.stat().st_mtime
                age_seconds = max(0, int(datetime.now().timestamp() - mtime))
                if age_seconds > ttl_seconds:
                    return None

            print("Getting cache")
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            # Corrupt or unreadable cache; ignore it
            return None

    def get_config(self) -> dict:
        """Load configuration from resources/config.json.

        Returns:
            The parsed configuration dictionary.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
        """
        path = RESOURCES_PATH / "config.json"
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
        raise FileNotFoundError(f"config.json not found in: {path}")

    def __format_times(self, issues: list[dict]) -> list[dict]:
        """Normalize ISO8601 timestamps from the API to DD-MM-YYYY strings."""
        for issue in issues:
            content = issue.get("content")
            if not isinstance(content, dict):
                continue
            for date_keys in self.date_keys:
                date_value = content.get(date_keys)
                if date_value is None:
                    continue
                # Safe to assign back since key exists in content
                content[date_keys] = utc_to_date(date_value)

        return issues

    def __filter_on_task(self, issues: list[dict]) -> list[dict]:
        """Filter issues to those labeled as tasks."""
        tasks = []
        for issue in issues:
            labels = issue["content"]["labels"]["nodes"]
            if len(labels) > 0 and "task" in labels[0].values():
                tasks.append(issue)

        return tasks

    def __filter_on_sprint(self, issues: list[dict]) -> list[dict]:
        """Include issues that were open at any time during the sprint.

        Overlap rule: [createdAt, closedAt or +inf) intersects
        [start_date, end_date].

        Args:
            issues: List of issue dictionaries as returned by the API.

        Returns:
            A filtered list containing only issues that overlapped the sprint.
        """
        included = []
        for issue in issues:
            content = issue.get("content", {})
            created_s = content.get("createdAt")
            closed_s = content.get("closedAt")

            if not created_s:
                continue  # cannot place the issue on a timeline without createdAt

            created = datetime.strptime(created_s, "%d-%m-%Y").date()
            closed = (
                datetime.strptime(closed_s, "%d-%m-%Y").date() if closed_s else None
            )

            # Overlaps the sprint if it existed at any time during [start_date, end_date]
            overlaps = created <= self.end_date and (
                closed is None or closed >= self.start_date
            )
            
            # Get the current sprint from field 'sprint'
            is_correct_sprint = False
            sprint = issue.get("sprint")
            
            if sprint is not None:
                sprint_num = int(sprint.get("number"))
                if sprint_num == self.config.get("sprint_data").get("sprint"):
                    is_correct_sprint = True
                                
            if overlaps and (sprint is None or is_correct_sprint is True):
                included.append(issue)

        return included

    def __create_dates(self) -> list[str]:
        """Build an inclusive list of day strings for the configured sprint."""
        # Parse into date objects (DD-MM-YYYY format)
        start_date = datetime.strptime(
            self.config["sprint_data"]["start_date"], "%d-%m-%Y"
        ).date()
        end_date = datetime.strptime(
            self.config["sprint_data"]["end_date"], "%d-%m-%Y"
        ).date()

        # Generate all days between start and end (inclusive)
        days = []
        current = start_date
        while current <= end_date:
            days.append(current.strftime("%d-%m-%Y"))
            current += timedelta(days=1)

        return days

    def fetch_and_plot_burndown_chart(self):
        """Fetch, cache, transform, and plot the sprint burndown chart."""
        # Try cache first (1 hour TTL). Set ttl_seconds=0 to always use when present
        # data = self.__check_and_get_cache(ttl_seconds=3600)
        data = None
        if data is None:
            print("Requesting data from github API")
            data = self.api_wrapper.get_request()

            # Persist fresh response to cache
            with open(RESOURCES_PATH / "data.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            
        nodes = (
            data.get("data", {})
            .get("user", {})
            .get("projectV2", {})
            .get("items", {})
            .get("nodes")
        )
        if not isinstance(nodes, list):
            pprint(data)
            return
        data = nodes
        data = self.__format_times(data)
        data = self.__filter_on_task(data)
        data = self.__filter_on_sprint(data)

        # Plot the issues
        self.burndown_chart.plot_burndown_chart(data)
        # pprint(data)
        print(self.sprint_dates)


if __name__ == "__main__":
    """Entry point to render the burndown chart when run as a script."""
    chart_generator = dataGenerator()
    chart_generator.fetch_and_plot_burndown_chart()
