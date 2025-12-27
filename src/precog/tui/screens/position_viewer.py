"""
Position Viewer Screen.

Display current positions with P&L calculations and history.

Design:
    - Summary panel showing total P&L
    - DataTable for position list
    - Position detail view on selection
    - Historical P&L chart (sparkline)

Reference:
    - Issue #283: TUI Additional Screens
    - ADR-018: Position Tracking with SCD Type 2
"""

from decimal import Decimal
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Label, Select, Static


class PositionViewerScreen(Screen):
    """
    Position viewer screen for monitoring trading positions.

    Displays all positions from the database with real-time P&L calculations.
    Positions can be filtered by status (open, closed, all).

    Educational Note:
        Positions use SCD Type 2 versioning (row_current_ind) which means
        the table contains the full history. We filter for current rows
        to show the latest state of each position.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh", "Refresh"),
        ("o", "show_open", "Open Only"),
        ("a", "show_all", "Show All"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create the position viewer layout."""
        yield Label("Position Viewer", id="screen-title", classes="screen-title")

        # Summary panel
        with Horizontal(id="summary-panel"):
            with Container(classes="summary-card"):
                yield Label("Open Positions", classes="summary-label")
                yield Static("0", id="open-count", classes="summary-value")
            with Container(classes="summary-card"):
                yield Label("Unrealized P&L", classes="summary-label")
                yield Static("$0.00", id="unrealized-pnl", classes="summary-value")
            with Container(classes="summary-card"):
                yield Label("Realized P&L", classes="summary-label")
                yield Static("$0.00", id="realized-pnl", classes="summary-value")
            with Container(classes="summary-card"):
                yield Label("Total P&L", classes="summary-label")
                yield Static("$0.00", id="total-pnl", classes="summary-value")

        # Filter bar
        with Horizontal(id="filter-bar"):
            yield Select(
                [
                    ("Open Positions", "open"),
                    ("Closed Positions", "closed"),
                    ("All Positions", "all"),
                ],
                id="status-filter",
                value="open",
            )

        # Position table
        with Container(id="table-container"):
            yield DataTable(id="position-table")

        # Detail panel
        with Container(id="detail-panel", classes="hidden"):
            yield Label("Position Details", classes="panel-header")
            yield Static("Select a position to view details", id="position-details")

        # Status bar
        yield Static("Loading positions...", id="position-status")

    def on_mount(self) -> None:
        """Initialize the position table and load data."""
        table = self.query_one("#position-table", DataTable)

        # Configure table columns
        table.add_columns(
            "ID",
            "Market",
            "Side",
            "Qty",
            "Entry",
            "Current",
            "P&L",
            "P&L %",
            "Status",
        )

        table.cursor_type = "row"
        table.zebra_stripes = True

        # Load initial data
        self._load_positions("open")

    def _load_positions(self, status_filter: str = "open") -> None:
        """
        Load positions from the database.

        Args:
            status_filter: Filter by status (open, closed, all)
        """
        table = self.query_one("#position-table", DataTable)
        table.clear()

        try:
            from precog.database.crud_operations import (  # type: ignore[attr-defined]
                get_positions_with_pnl,
            )

            positions = get_positions_with_pnl(
                status=None if status_filter == "all" else status_filter,
                limit=100,
            )

            total_unrealized = Decimal("0")
            total_realized = Decimal("0")
            open_count = 0

            for pos in positions:
                pnl = pos.get("unrealized_pnl", Decimal("0"))
                pnl_pct = pos.get("pnl_percent", Decimal("0"))

                # Color based on P&L
                pnl_str = f"${pnl:+.2f}"
                if pnl > 0:
                    pnl_str = f"[green]{pnl_str}[/]"
                elif pnl < 0:
                    pnl_str = f"[red]{pnl_str}[/]"

                pnl_pct_str = f"{pnl_pct:+.1f}%"
                if pnl_pct > 0:
                    pnl_pct_str = f"[green]{pnl_pct_str}[/]"
                elif pnl_pct < 0:
                    pnl_pct_str = f"[red]{pnl_pct_str}[/]"

                table.add_row(
                    str(pos.get("position_id", "")),
                    pos.get("ticker", "")[:20],
                    pos.get("side", "").upper(),
                    str(pos.get("quantity", 0)),
                    f"${pos.get('entry_price', Decimal('0')):.2f}",
                    f"${pos.get('current_price', Decimal('0')):.2f}",
                    pnl_str,
                    pnl_pct_str,
                    pos.get("status", "").title(),
                )

                if pos.get("status") == "open":
                    open_count += 1
                    total_unrealized += pnl
                else:
                    total_realized += pos.get("realized_pnl", Decimal("0"))

            self._update_summary(open_count, total_unrealized, total_realized)
            self.query_one("#position-status", Static).update(
                f"[green]Loaded {len(positions)} positions[/]"
            )

        except ImportError:
            self._load_demo_data(table)
        except Exception as e:
            self.query_one("#position-status", Static).update(
                f"[red]Error loading positions: {e}[/]"
            )
            self._load_demo_data(table)

    def _load_demo_data(self, table: DataTable) -> None:
        """Load demonstration data when database is unavailable."""
        demo_positions = [
            (
                "1",
                "KXNFL-KC-BUF",
                "YES",
                "100",
                "$0.55",
                "$0.62",
                "[green]+$7.00[/]",
                "[green]+12.7%[/]",
                "Open",
            ),
            (
                "2",
                "KXNFL-SF-GB",
                "YES",
                "50",
                "$0.60",
                "$0.58",
                "[red]-$1.00[/]",
                "[red]-3.3%[/]",
                "Open",
            ),
            (
                "3",
                "KXNBA-LAL-BOS",
                "NO",
                "75",
                "$0.52",
                "$0.48",
                "[green]+$3.00[/]",
                "[green]+7.7%[/]",
                "Open",
            ),
            (
                "4",
                "KXNCAAF-OSU-MICH",
                "YES",
                "200",
                "$0.45",
                "$0.51",
                "[green]+$12.00[/]",
                "[green]+13.3%[/]",
                "Closed",
            ),
        ]

        for pos in demo_positions:
            table.add_row(*pos)

        self._update_summary(3, Decimal("9.00"), Decimal("12.00"))
        self.query_one("#position-status", Static).update(
            "[yellow]Showing demo data (database unavailable)[/]"
        )

    def _update_summary(self, open_count: int, unrealized: Decimal, realized: Decimal) -> None:
        """Update summary panel values."""
        total = unrealized + realized

        self.query_one("#open-count", Static).update(str(open_count))

        # Unrealized P&L with color
        unrealized_str = f"${unrealized:+.2f}"
        if unrealized > 0:
            unrealized_str = f"[green]{unrealized_str}[/]"
        elif unrealized < 0:
            unrealized_str = f"[red]{unrealized_str}[/]"
        self.query_one("#unrealized-pnl", Static).update(unrealized_str)

        # Realized P&L with color
        realized_str = f"${realized:+.2f}"
        if realized > 0:
            realized_str = f"[green]{realized_str}[/]"
        elif realized < 0:
            realized_str = f"[red]{realized_str}[/]"
        self.query_one("#realized-pnl", Static).update(realized_str)

        # Total P&L with color
        total_str = f"${total:+.2f}"
        if total > 0:
            total_str = f"[bold green]{total_str}[/]"
        elif total < 0:
            total_str = f"[bold red]{total_str}[/]"
        self.query_one("#total-pnl", Static).update(total_str)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle filter dropdown changes."""
        if event.select.id == "status-filter":
            self._load_positions(str(event.value))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle position row selection."""
        table = self.query_one("#position-table", DataTable)
        row_data = table.get_row(event.row_key)

        if row_data:
            details = f"""
[bold]Position ID:[/] {row_data[0]}
[bold]Market:[/] {row_data[1]}
[bold]Side:[/] {row_data[2]}
[bold]Quantity:[/] {row_data[3]}
[bold]Entry Price:[/] {row_data[4]}
[bold]Current Price:[/] {row_data[5]}
[bold]P&L:[/] {row_data[6]}
[bold]P&L %:[/] {row_data[7]}
[bold]Status:[/] {row_data[8]}
"""
            self.query_one("#position-details", Static).update(details)
            self.query_one("#detail-panel").remove_class("hidden")

    def action_refresh(self) -> None:
        """Refresh position data."""
        status = self.query_one("#status-filter", Select).value
        self._load_positions(str(status) if status else "open")
        self.app.notify("Positions refreshed")

    def action_show_open(self) -> None:
        """Filter to open positions only."""
        self.query_one("#status-filter", Select).value = "open"
        self._load_positions("open")

    def action_show_all(self) -> None:
        """Show all positions."""
        self.query_one("#status-filter", Select).value = "all"
        self._load_positions("all")

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
