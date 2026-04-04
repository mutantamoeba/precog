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
from textual.widgets import DataTable, Label, Select, Static

from precog.tui.screens.base_screen import BaseScreen
from precog.tui.widgets.breadcrumb import Breadcrumb
from precog.tui.widgets.environment_bar import EnvironmentBar


class PositionViewerScreen(BaseScreen):
    """
    Position viewer screen for monitoring trading positions.

    Displays all positions from the database with real-time P&L calculations.
    Positions can be filtered by status (open, closed, all).

    Educational Note:
        Positions use SCD Type 2 versioning (row_current_ind) which means
        the table contains the full history. We filter for current rows
        to show the latest state of each position.
        Inherits from BaseScreen to get global keybindings in footer.
    """

    BINDINGS: ClassVar[list[BindingType]] = BaseScreen.BINDINGS + [
        ("r", "refresh", "Refresh"),
        ("o", "show_open", "Open Only"),
        ("a", "show_all", "Show All"),
        ("n", "next_page", "Next Page"),
        ("p", "prev_page", "Prev Page"),
    ]

    PAGE_SIZE = 50

    def compose(self) -> ComposeResult:
        """Create the position viewer layout."""
        yield Breadcrumb.for_screen("position_viewer")
        yield EnvironmentBar.from_app(self.app)
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

        # Pagination state
        self._current_page = 0

        # Load initial data
        self._load_positions("open")

    def _get_data_source_mode(self) -> str:
        """Get the current data source mode from the app.

        Educational Note:
            Accesses the app's data_source_mode property which controls whether
            screens use real database data, demo data, or auto-fallback behavior.
        """
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.data_source_mode
        return "auto"  # Default to auto mode

    def _load_positions(self, status_filter: str = "open") -> None:
        """
        Load positions from the database.

        Args:
            status_filter: Filter by status (open, closed, all)

        Educational Note:
            The data source mode determines behavior:
            - "demo": Always use demo data, skip database query
            - "real": Only use database, show error if unavailable
            - "auto": Try database first, fall back to demo on error
        """
        table = self.query_one("#position-table", DataTable)
        table.clear()

        data_mode = self._get_data_source_mode()

        # Demo mode: Skip database, use demo data directly
        if data_mode == "demo":
            self._load_demo_data(table, status_filter=status_filter)
            return

        try:
            from precog.database.crud_positions import get_positions_with_pnl

            positions = get_positions_with_pnl(
                status=None if status_filter == "all" else status_filter,
                limit=self.PAGE_SIZE,
                offset=self._current_page * self.PAGE_SIZE,
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
            page_info = f"Page {self._current_page + 1}"
            has_more = len(positions) == self.PAGE_SIZE
            if has_more:
                page_info += " | [dim]n=Next[/]"
            if self._current_page > 0:
                page_info = "[dim]p=Prev[/] | " + page_info
            self.query_one("#position-status", Static).update(
                f"[green]Loaded {len(positions)} positions[/] | {page_info}"
            )

        except ImportError:
            if data_mode == "real":
                self.query_one("#position-status", Static).update(
                    "[red]Database module not available - real mode requires database[/]"
                )
            else:
                self._load_demo_data(table, status_filter=status_filter)
        except Exception as e:
            if data_mode == "real":
                self.query_one("#position-status", Static).update(f"[red]Database error: {e}[/]")
            else:
                # Auto mode: fall back to demo data after showing error
                self._load_demo_data(table, status_filter=status_filter)

    def _load_demo_data(self, table: DataTable, status_filter: str = "open") -> None:
        """Load demonstration data when database is unavailable.

        Args:
            table: The DataTable to populate
            status_filter: Filter by status (open, closed, all)

        Educational Note:
            Demo data includes both open and closed positions to allow
            users to test the filtering functionality. P&L values are
            pre-calculated for display, matching real position format.
        """
        # Full demo dataset with raw values for proper filtering and calculations
        # Format: (id, ticker, side, qty, entry, current, pnl, pnl_pct, status, raw_pnl, raw_realized)
        all_demo_positions = [
            # Open positions (unrealized P&L)
            (
                "1",
                "KXNFL-KC-BUF",
                "YES",
                "100",
                "$0.55",
                "$0.62",
                Decimal("7.00"),
                Decimal("12.7"),
                "Open",
            ),
            (
                "2",
                "KXNFL-SF-GB",
                "YES",
                "50",
                "$0.60",
                "$0.58",
                Decimal("-1.00"),
                Decimal("-3.3"),
                "Open",
            ),
            (
                "3",
                "KXNBA-LAL-BOS",
                "NO",
                "75",
                "$0.52",
                "$0.48",
                Decimal("3.00"),
                Decimal("7.7"),
                "Open",
            ),
            (
                "5",
                "KXNHL-TOR-MTL",
                "YES",
                "60",
                "$0.45",
                "$0.52",
                Decimal("4.20"),
                Decimal("15.6"),
                "Open",
            ),
            # Closed positions (realized P&L)
            (
                "4",
                "KXNCAAF-OSU-MICH",
                "YES",
                "200",
                "$0.45",
                "$0.51",
                Decimal("12.00"),
                Decimal("13.3"),
                "Closed",
            ),
            (
                "6",
                "KXMLB-NYY-BOS",
                "NO",
                "150",
                "$0.48",
                "$0.35",
                Decimal("19.50"),
                Decimal("27.1"),
                "Closed",
            ),
            (
                "7",
                "KXNCAAB-DUKE-UNC",
                "YES",
                "80",
                "$0.55",
                "$0.42",
                Decimal("-10.40"),
                Decimal("-23.6"),
                "Closed",
            ),
        ]

        # Apply status filter
        filtered_positions = []
        for pos in all_demo_positions:
            pos_status = pos[8].lower()
            if status_filter == "all" or pos_status == status_filter.lower():
                filtered_positions.append(pos)

        # Apply pagination
        total_filtered = len(filtered_positions)
        start = self._current_page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_positions = filtered_positions[start:end]

        # Calculate summary metrics from paginated data
        open_count = 0
        total_unrealized = Decimal("0")
        total_realized = Decimal("0")

        for pos in page_positions:
            pos_id, ticker, side, qty, entry, current, pnl, pnl_pct, status = pos

            # Format P&L with color
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

            table.add_row(pos_id, ticker, side, qty, entry, current, pnl_str, pnl_pct_str, status)

            # Track metrics
            if status.lower() == "open":
                open_count += 1
                total_unrealized += pnl
            else:
                total_realized += pnl

        # Update summary with calculated values
        self._update_summary(open_count, total_unrealized, total_realized)

        # Status message with filter and pagination info
        filter_info = ""
        if status_filter != "all":
            filter_info = f" | Filter: {status_filter.title()}"

        page_info = f"Page {self._current_page + 1}"
        has_more = end < total_filtered
        if has_more:
            page_info += " | [dim]n=Next[/]"
        if self._current_page > 0:
            page_info = "[dim]p=Prev[/] | " + page_info

        self.query_one("#position-status", Static).update(
            f"[bold yellow on #3D2A00]  SAMPLE DATA  [/] "
            f"[dim]Showing {len(page_positions)} of {total_filtered} demo positions{filter_info}[/] | {page_info}"
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
            self._current_page = 0
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

    def action_next_page(self) -> None:
        """Navigate to the next page of results."""
        table = self.query_one("#position-table", DataTable)
        if table.row_count < self.PAGE_SIZE:
            self.app.notify("Already on last page")
            return
        self._current_page += 1
        status = self.query_one("#status-filter", Select).value
        self._load_positions(str(status) if status else "open")

    def action_prev_page(self) -> None:
        """Navigate to the previous page of results."""
        if self._current_page > 0:
            self._current_page -= 1
            status = self.query_one("#status-filter", Select).value
            self._load_positions(str(status) if status else "open")

    def action_show_open(self) -> None:
        """Filter to open positions only."""
        self._current_page = 0
        self.query_one("#status-filter", Select).value = "open"
        self._load_positions("open")

    def action_show_all(self) -> None:
        """Show all positions."""
        self._current_page = 0
        self.query_one("#status-filter", Select).value = "all"
        self._load_positions("all")

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
