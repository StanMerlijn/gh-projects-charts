"""Generate charts from GitHub Projects data.

This module contains the high-level orchestration to fetch project items via
the GitHub GraphQL API, cache the response, preprocess the data into a time
series, and render a burndown chart using Matplotlib.
"""
from util import utc_to_date
from datetime import datetime, timedelta
from api_wrapper import Api_wrapper
from pathlib import Path
from pprint import pprint
import json
from typing import Optional
from dataclasses import dataclass
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

FILE_PATH = Path(__file__).parent.resolve()
RESOURCES_PATH = FILE_PATH / "resources"


@dataclass
class Burndown_data:
    """Container for all inputs to the burndown plotting routine.

    Attributes:
        total_issues: Total number of issues considered in the sprint window.
        dates: List of day strings ("DD-MM-YYYY") composing the x-axis.
        open_issues: Count of open issues for each date.
        unassigned_open_issues: Optional series for unassigned open issues.
    """
    total_issues: int  # Changed from str to int
    dates: list[str] # X dataset
    open_issues: list[int] # Y datasets (renamed from closed)
    unassigned_open_issues: list[int]  
        
        
class Chart_generator:
    """Drive data collection, transformation, and chart rendering."""
    def __init__(self) -> None:
        """Load configuration, compute date range, and initialize API client."""
        self.config = self.get_config()
        self.dates = self.create_dates()
        self.date_keys = ["closedAt", "createdAt"]
        self.api_wrapper = Api_wrapper(self.config, RESOURCES_PATH)
        
        self.start_date: datetime  = datetime.strptime(self.config["start_date"], "%d-%m-%Y").date()
        self.end_date: datetime    = datetime.strptime(self.config["end_date"], "%d-%m-%Y").date()
        
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
    
    def create_dates(self) -> list[str]:
        """Build an inclusive list of day strings for the configured sprint."""
        # Parse into date objects (DD-MM-YYYY format)
        start_date = datetime.strptime(self.config["start_date"], "%d-%m-%Y").date()
        end_date = datetime.strptime(self.config["end_date"], "%d-%m-%Y").date()

        # Generate all days between start and end (inclusive)
        days = []
        current = start_date
        while current <= end_date:
            days.append(current.strftime("%d-%m-%Y"))
            current += timedelta(days=1)
        
        return days

    def check_and_get_cache(self, ttl_seconds: int = 3600, force_refresh: bool = False) -> Optional[dict]:
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

    def plot_burndown_chart(self, burndown_data: Burndown_data):
        """Plot the burndown chart showing open issues over time.

        Args:
            burndown_data: Prepared series containing dates and open issue counts.
        """
        # Convert date strings to datetime objects for better plotting
        dates = [datetime.strptime(date, "%d-%m-%Y") for date in burndown_data.dates]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, burndown_data.open_issues, label="Issues open", linewidth=2, markersize=4)

        # Overlay: Unassigned open issues
        if burndown_data.unassigned_open_issues:
            ax.plot(dates, burndown_data.unassigned_open_issues, linestyle=":", color="orange",linewidth=2,label="Unassigned open")

        # No extra space before first/last label
        ax.margins(x=0,y=0)
        ax.set_xlim(dates[0], dates[-1])

        # Formatting
        sprint_label = self.config.get("sprint") or f"{self.start_date.strftime('%d-%m')}–{self.end_date.strftime('%d-%m')}"
        ax.set_title(f"Sprint {sprint_label} Burndown Chart", fontsize=16, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Open Issues", fontsize=12)
        ax.grid(True, alpha=0.3)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m-%Y"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.setp(ax.get_xticklabels(), rotation=45)

        # Ideal burndown
        total_issues = burndown_data.total_issues
        if len(dates) > 1:
            ideal_line = [total_issues - (i * total_issues / (len(dates) - 1)) for i in range(len(dates))]
        else:
            ideal_line = [total_issues]
        ax.plot(dates, ideal_line, "--", alpha=0.7, color="grey", label="Ideal Burndown")

        ax.legend()
        fig.tight_layout()
        plt.show()
        
    def generate_charts(self):
        """Fetch, cache, transform, and plot the sprint burndown chart."""
        # Try cache first (1 hour TTL). Set ttl_seconds=0 to always use when present
        data = self.check_and_get_cache(ttl_seconds=3600)
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
        
        data = self.format_times(data)
        data = self.filter_on_sprint(data)
        
        data_burndown_chart = self.prep_data_for_burndown_chart(data)
        # pprint(data)
        print(self.dates)
        
        # Plot the burndown chart
        self.plot_burndown_chart(data_burndown_chart)
            
    def format_times(self, issues: list[dict]) -> list[dict]:
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
    
    def filter_on_sprint(self, issues: list[dict]) -> list[dict]:
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
            closed_s  = content.get("closedAt")

            if not created_s:
                continue  # cannot place the issue on a timeline without createdAt

            created = datetime.strptime(created_s, "%d-%m-%Y").date()
            closed  = datetime.strptime(closed_s, "%d-%m-%Y").date() if closed_s else None

            # Overlaps the sprint if it existed at any time during [start_date, end_date]
            overlaps = created <= self.end_date and (closed is None or closed >= self.start_date)
            if overlaps:
                included.append(issue)
                
        return included
    
    def prep_data_for_burndown_chart(self, issues: list[dict]) -> Burndown_data:
        """Prepare burndown inputs by counting open issues per day.

        Args:
            issues: Filtered list of issues within/overlapping the sprint.

        Returns:
            A `Burndown_data` instance consumable by the plotting function.
        """
        # Get the num open issues per day
        open_issues = []
        
        for date in self.dates:
            current_date = datetime.strptime(date, "%d-%m-%Y").date()
            num_issues_open = 0
            
            for issue in issues:
                content = issue.get("content") or {}
                date_value = content.get("closedAt")
                    
                if date_value is None:
                    num_issues_open += 1
                    continue
                
                # if is open
                if current_date <= datetime.strptime(date_value, "%d-%m-%Y").date():
                    num_issues_open += 1 
                    
            open_issues.append(num_issues_open)
            
        print(open_issues)

        return Burndown_data(
            total_issues=len(issues),
            dates=self.dates,
            open_issues=open_issues,
            unassigned_open_issues=None
        )
        
if __name__ == "__main__":
    """Entry point to render the burndown chart when run as a script."""
    chart_generator = Chart_generator()
    chart_generator.generate_charts()
    
