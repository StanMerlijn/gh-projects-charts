"""
@file burndown_chart.py
@brief Plot and optionally save a sprint burndown chart.
@details Expects issues with content.createdAt/closedAt (DD-MM-YYYY) and a list of sprint dates.
@author gh-projects-charts maintainers
@date 2025-11-05
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

FILE_PATH = Path(__file__).parent.resolve()


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
    dates: list[str]  # X dataset
    open_issues: list[int]  # Y datasets (renamed from closed)
    unassigned_open_issues: list[int]


class BurndownChart:
    """Class to plot and or save the project data into a burndown chart"""
    
    def __init__(
        self, config: dict, dates: list[str], start_date: datetime, end_date: datetime
    ):
        self.config = config
        self.sprint_dates = dates
        self.start_date = start_date
        self.end_date = end_date

    def __prepare_burndown_data(self, issues: list[dict]) -> Burndown_data:
        """Prepare burndown inputs by counting open issues per day.

        Args:
            issues: Filtered list of issues within/overlapping the sprint.

        Returns:
            A `Burndown_data` instance consumable by the plotting function.
        """
        # Get the num open issues per day
        open_issues = []

        for date in self.sprint_dates:
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
            dates=self.sprint_dates,
            open_issues=open_issues,
            unassigned_open_issues=None,
        )

    def __display_and_save_plot(self, plt: plt) -> None:
        """
        Display and/or save the current Matplotlib figure based on runtime configuration.
        Behavior:
        - If self.config['wants_to_display'] is true, the plot is shown via plt.show().
        - If self.config['wants_to_save'] is true, the plot is saved to the charts folder EE

        Args:
                plt: A matplotlib.pyplot-like interface used to show and save the current figure.
        """
        if self.config["wants_to_save"]:
            charts_dir = (
                FILE_PATH.parent
                / "charts"
                / f"Burndown_chart_sprint_{self.config['sprint_data']['sprint']}"
            )
            plt.savefig(charts_dir, dpi=400)

        if self.config["wants_to_display"]:
            plt.show()

    def plot_burndown_chart(self, issues: list[dict]) -> None:
        """
        Plot a sprint burndown chart of open issues over time using Matplotlib.
        This method builds a time series from the instance's issues and visualizes:
        - The number of open issues per day ("Tasks open").
        - An optional overlay of unassigned open issues (if available in the data).
        - An ideal burndown reference line that linearly decreases from the total
            number of issues to zero across the sprint duration.

        Args:
            issues: Filtered list of issues within/overlapping the sprint.
        Raises:
                RuntimeError: If `self.issues` is not defined.
        Notes:
                - This method relies on instance attributes: `issues`, `config`, `start_date`,
                    and `end_date`.
                - Data preparation is performed by an internal helper that produces:
                    dates (DD-MM-YYYY), open_issues, optional unassigned_open_issues, and
                    total_issues.
                - Displays a Matplotlib window (behavior may vary by backend).

        """
        burndown_data = self.__prepare_burndown_data(issues)

        # Convert date strings to datetime objects for better plotting
        sprint_dates = [
            datetime.strptime(date, "%d-%m-%Y") for date in burndown_data.dates
        ]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(
            sprint_dates,
            burndown_data.open_issues,
            label="Tasks open",
            linewidth=2,
            markersize=4,
        )

        # Overlay: Unassigned open issues
        if burndown_data.unassigned_open_issues:
            ax.plot(
                sprint_dates,
                burndown_data.unassigned_open_issues,
                linestyle=":",
                color="orange",
                linewidth=2,
                label="Unassigned open",
            )

        # No extra space before first/last label
        ax.margins(x=0, y=0)
        ax.set_xlim(sprint_dates[0], sprint_dates[-1])

        # Formatting
        ax.set_title(
            f"Sprint {self.config['sprint_data']['sprint']} Burndown Chart",
            fontsize=16,
            fontweight="bold",
        )
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Open tasks", fontsize=12)
        ax.grid(True, alpha=0.3)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m-%Y"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.setp(ax.get_xticklabels(), rotation=45)

        # Ideal burndown
        total_issues = burndown_data.total_issues
        if len(sprint_dates) > 1:
            ideal_line = [
                total_issues - (i * total_issues / (len(sprint_dates) - 1))
                for i in range(len(sprint_dates))
            ]
        else:
            ideal_line = [total_issues]
        ax.plot(
            sprint_dates,
            ideal_line,
            "--",
            alpha=0.7,
            color="grey",
            label="Ideal Burndown",
        )

        ax.legend()
        fig.tight_layout()

        self.__display_and_save_plot(plt)
