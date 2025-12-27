"""
Market Browser Screen.

Browse Kalshi markets with filtering by sport, status, and search.
Displays live market data from the database.

Design:
    - DataTable for market list with sorting
    - Filter bar at top (sport, status, search)
    - Detail panel on selection
    - Refresh on interval

Reference:
    - Issue #283: TUI Additional Screens
    - Textual DataTable: https://textual.textualize.io/widgets/data_table/
"""

from decimal import Decimal
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, Select, Static


class MarketBrowserScreen(Screen):
    """
    Market browser screen for viewing and filtering Kalshi markets.

    Displays markets from the database with real-time filtering.
    Markets are fetched from the markets table and can be filtered
    by sport, status, or search term.

    Educational Note:
        This screen demonstrates the Textual DataTable widget which
        provides Excel-like functionality with sorting and selection.
        Data is loaded asynchronously to keep the UI responsive.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh", "Refresh"),
        ("f", "focus_filter", "Filter"),
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create the market browser layout."""
        yield Label("Market Browser", id="screen-title", classes="screen-title")

        # Filter bar
        with Horizontal(id="filter-bar"):
            yield Select(
                [
                    ("All Sports", "all"),
                    ("NFL", "nfl"),
                    ("NBA", "nba"),
                    ("NHL", "nhl"),
                    ("NCAAF", "ncaaf"),
                    ("NCAAB", "ncaab"),
                    ("MLB", "mlb"),
                ],
                id="sport-filter",
                prompt="Sport",
            )
            yield Select(
                [
                    ("All Status", "all"),
                    ("Open", "open"),
                    ("Closed", "closed"),
                    ("Settled", "settled"),
                ],
                id="status-filter",
                prompt="Status",
            )
            yield Input(placeholder="Search markets...", id="search-input")

        # Market table
        with Container(id="table-container"):
            yield DataTable(id="market-table")

        # Detail panel (shown on selection)
        with Container(id="detail-panel", classes="hidden"):
            yield Label("Market Details", classes="panel-header")
            yield Static("Select a market to view details", id="market-details")

        # Status bar
        yield Static("Loading markets...", id="market-status")

    def on_mount(self) -> None:
        """Initialize the market table and load data."""
        table = self.query_one("#market-table", DataTable)

        # Configure table columns
        table.add_columns(
            "Ticker",
            "Title",
            "Sport",
            "Yes Price",
            "No Price",
            "Status",
            "Volume",
        )

        # Styling
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Load initial data
        self._load_markets()

    def _load_markets(self, sport: str = "all", status: str = "all", search: str = "") -> None:
        """
        Load markets from the database with filters.

        Args:
            sport: Sport filter (all, nfl, nba, etc.)
            status: Status filter (all, open, closed, settled)
            search: Search term for ticker/title
        """
        table = self.query_one("#market-table", DataTable)
        table.clear()

        try:
            # Try to fetch from database
            from precog.database.crud_operations import (  # type: ignore[attr-defined]
                get_markets_summary,
            )

            markets = get_markets_summary(
                sport=None if sport == "all" else sport,
                status=None if status == "all" else status,
                search=search if search else None,
                limit=100,
            )

            for market in markets:
                table.add_row(
                    market.get("ticker", ""),
                    market.get("title", "")[:50],  # Truncate long titles
                    market.get("sport", "").upper(),
                    f"${market.get('yes_price', Decimal('0')):.2f}",
                    f"${market.get('no_price', Decimal('0')):.2f}",
                    market.get("status", "").title(),
                    f"{market.get('volume', 0):,}",
                )

            self.query_one("#market-status", Static).update(
                f"[green]Loaded {len(markets)} markets[/]"
            )

        except ImportError:
            # Database not available, show demo data
            self._load_demo_data(table)
        except Exception as e:
            self.query_one("#market-status", Static).update(f"[red]Error loading markets: {e}[/]")
            self._load_demo_data(table)

    def _load_demo_data(self, table: DataTable) -> None:
        """Load demonstration data when database is unavailable."""
        demo_markets = [
            ("KXNFL-KC-BUF", "Chiefs vs Bills Winner", "NFL", "$0.55", "$0.45", "Open", "12,345"),
            ("KXNFL-SF-GB", "49ers vs Packers Winner", "NFL", "$0.62", "$0.38", "Open", "8,901"),
            ("KXNBA-LAL-BOS", "Lakers vs Celtics Winner", "NBA", "$0.48", "$0.52", "Open", "5,678"),
            ("KXNHL-TOR-MTL", "Maple Leafs vs Canadiens", "NHL", "$0.58", "$0.42", "Open", "3,456"),
            (
                "KXNCAAF-OSU-MICH",
                "Ohio State vs Michigan",
                "NCAAF",
                "$0.51",
                "$0.49",
                "Closed",
                "15,789",
            ),
        ]

        for market in demo_markets:
            table.add_row(*market)

        self.query_one("#market-status", Static).update(
            "[yellow]Showing demo data (database unavailable)[/]"
        )

    def on_select_changed(self, event: Select.Changed) -> None:  # noqa: ARG002
        """Handle filter dropdown changes."""
        self._apply_filters()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        # Debounce would be nice here, but for simplicity we refresh immediately
        if event.input.id == "search-input":
            self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filter values to reload markets."""
        sport = self.query_one("#sport-filter", Select).value
        status = self.query_one("#status-filter", Select).value
        search = self.query_one("#search-input", Input).value

        self._load_markets(
            sport=str(sport) if sport else "all",
            status=str(status) if status else "all",
            search=search,
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle market row selection to show details."""
        table = self.query_one("#market-table", DataTable)
        row_data = table.get_row(event.row_key)

        if row_data:
            details = f"""
[bold]Ticker:[/] {row_data[0]}
[bold]Title:[/] {row_data[1]}
[bold]Sport:[/] {row_data[2]}
[bold]Yes Price:[/] {row_data[3]}
[bold]No Price:[/] {row_data[4]}
[bold]Status:[/] {row_data[5]}
[bold]Volume:[/] {row_data[6]}
"""
            self.query_one("#market-details", Static).update(details)
            self.query_one("#detail-panel").remove_class("hidden")

    def action_refresh(self) -> None:
        """Refresh market data."""
        self._apply_filters()
        self.app.notify("Markets refreshed")

    def action_focus_filter(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_go_back(self) -> None:
        """Return to main menu."""
        self.app.pop_screen()
