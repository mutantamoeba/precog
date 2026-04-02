"""
Market Browser Screen.

Browse Kalshi markets with filtering by sport, status, and search.
Displays live market data from the database OR directly from Kalshi API.

Design:
    - DataTable for market list with sorting
    - Filter bar at top (sport, status, search)
    - Detail panel on selection
    - Refresh on interval
    - Multi-source data: Database → Kalshi API → Demo data fallback

Reference:
    - Issue #283: TUI Additional Screens
    - Textual DataTable: https://textual.textualize.io/widgets/data_table/
"""

from decimal import Decimal
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from precog.tui.screens.base_screen import BaseScreen
from precog.tui.widgets.breadcrumb import Breadcrumb
from precog.tui.widgets.environment_bar import EnvironmentBar
from precog.utils.logger import get_logger

logger = get_logger(__name__)


class MarketBrowserScreen(BaseScreen):
    """
    Market browser screen for viewing and filtering Kalshi markets.

    Displays markets from the database with real-time filtering.
    Markets are fetched from the markets table and can be filtered
    by sport, status, or search term.

    Educational Note:
        This screen demonstrates the Textual DataTable widget which
        provides Excel-like functionality with sorting and selection.
        Data is loaded asynchronously to keep the UI responsive.
        Inherits from BaseScreen to get global keybindings in footer.
    """

    BINDINGS: ClassVar[list[BindingType]] = BaseScreen.BINDINGS + [
        ("r", "refresh", "Refresh"),
        ("a", "fetch_from_api", "Fetch API"),
        ("f", "focus_filter", "Filter"),
        ("n", "next_page", "Next Page"),
        ("p", "prev_page", "Prev Page"),
    ]

    PAGE_SIZE = 50

    def compose(self) -> ComposeResult:
        """Create the market browser layout."""
        yield Breadcrumb.for_screen("market_browser")
        yield EnvironmentBar.from_app(self.app)
        yield Label("Market Browser", id="screen-title", classes="screen-title")

        # Filter bar
        # Educational Note: Select widgets need a default value= to avoid returning
        # Select.BLANK when first rendered. Without it, filters would incorrectly
        # filter out all records on initial load.
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
                value="all",
            )
            yield Select(
                [
                    ("All Status", "all"),
                    ("Open", "open"),
                    ("Closed", "closed"),
                    ("Settled", "settled"),
                ],
                id="status-filter",
                value="all",
            )
            yield Input(placeholder="Search markets...", id="search-input")
            yield Button("Fetch from API", id="btn-fetch-api", variant="primary")

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

        # Pagination state
        self._current_page = 0

        # Load initial data
        self._load_markets()

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

    def _get_api_environment(self) -> str:
        """Get the current API environment from the app.

        Educational Note:
            The API environment controls which Kalshi endpoint is used:
            - "demo": Paper trading with test accounts (demo-api.kalshi.com)
            - "production": Real money trading (trading-api.kalshi.com)
        """
        from precog.tui.app import PrecogApp

        if isinstance(self.app, PrecogApp):
            return self.app.api_environment
        return "demo"  # Default to demo for safety

    def _load_markets(self, sport: str = "all", status: str = "all", search: str = "") -> None:
        """
        Load markets from the database with filters.

        Args:
            sport: Sport filter (all, nfl, nba, etc.)
            status: Status filter (all, open, closed, settled)
            search: Search term for ticker/title

        Educational Note:
            The data source mode determines behavior:
            - "demo": Always use demo data, skip database query
            - "real": Only use database, show error if unavailable
            - "auto": Try database first, fall back to demo on error
        """
        table = self.query_one("#market-table", DataTable)
        table.clear()

        data_mode = self._get_data_source_mode()

        # Demo mode: Skip database, use demo data directly
        if data_mode == "demo":
            self._load_demo_data(table, sport=sport, status=status, search=search)
            return

        try:
            # Try to fetch from database
            from precog.database.crud_operations import get_markets_summary

            markets = get_markets_summary(
                sport=None if sport == "all" else sport,
                status=None if status == "all" else status,
                search=search if search else None,
                limit=self.PAGE_SIZE,
                offset=self._current_page * self.PAGE_SIZE,
            )

            for market in markets:
                table.add_row(
                    market.get("ticker", ""),
                    market.get("title", "")[:50],  # Truncate long titles
                    market.get("subcategory", "").upper(),
                    f"${market.get('yes_ask_price', Decimal('0')):.2f}",
                    f"${market.get('no_ask_price', Decimal('0')):.2f}",
                    market.get("status", "").title(),
                    f"{market.get('volume', 0):,}",
                )

            page_info = f"Page {self._current_page + 1}"
            has_more = len(markets) == self.PAGE_SIZE
            if has_more:
                page_info += " | [dim]n=Next[/]"
            if self._current_page > 0:
                page_info = "[dim]p=Prev[/] | " + page_info
            self.query_one("#market-status", Static).update(
                f"[green]Loaded {len(markets)} markets[/] | {page_info}"
            )

        except ImportError:
            if data_mode == "real":
                self.query_one("#market-status", Static).update(
                    "[red]Database module not available - real mode requires database[/]"
                )
            else:
                # Auto mode: fall back to demo data
                self._load_demo_data(table, sport=sport, status=status, search=search)
        except Exception as e:
            if data_mode == "real":
                self.query_one("#market-status", Static).update(f"[red]Database error: {e}[/]")
            else:
                # Auto mode: fall back to demo data
                self.query_one("#market-status", Static).update(
                    f"[red]Error loading markets: {e}[/]"
                )
                self._load_demo_data(table, sport=sport, status=status, search=search)

    def _load_demo_data(
        self, table: DataTable, sport: str = "all", status: str = "all", search: str = ""
    ) -> None:
        """Load demonstration data when database is unavailable.

        Args:
            table: The DataTable to populate
            sport: Sport filter (all, nfl, nba, etc.)
            status: Status filter (all, open, closed, settled)
            search: Search term for ticker/title

        Educational Note:
            Demo data is clearly labeled to prevent confusion with real
            market data. This follows the principle of "explicit over clever" -
            users should always know when they're viewing sample data.
            Filters work on demo data so users can test the UI functionality.
        """
        # Full demo dataset
        all_demo_markets = [
            ("KXNFL-KC-BUF", "Chiefs vs Bills Winner", "NFL", "$0.55", "$0.45", "Open", "12,345"),
            ("KXNFL-SF-GB", "49ers vs Packers Winner", "NFL", "$0.62", "$0.38", "Open", "8,901"),
            (
                "KXNFL-DAL-PHI",
                "Cowboys vs Eagles Winner",
                "NFL",
                "$0.44",
                "$0.56",
                "Closed",
                "9,234",
            ),
            ("KXNBA-LAL-BOS", "Lakers vs Celtics Winner", "NBA", "$0.48", "$0.52", "Open", "5,678"),
            (
                "KXNBA-GSW-MIA",
                "Warriors vs Heat Winner",
                "NBA",
                "$0.67",
                "$0.33",
                "Settled",
                "4,567",
            ),
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
            ("KXNCAAF-ALA-UGA", "Alabama vs Georgia", "NCAAF", "$0.45", "$0.55", "Open", "11,234"),
            (
                "KXNCAAB-DUKE-UNC",
                "Duke vs North Carolina",
                "NCAAB",
                "$0.53",
                "$0.47",
                "Open",
                "6,789",
            ),
            (
                "KXMLB-NYY-BOS",
                "Yankees vs Red Sox Winner",
                "MLB",
                "$0.52",
                "$0.48",
                "Settled",
                "7,890",
            ),
        ]

        # Apply filters to demo data
        filtered_markets = []
        for market in all_demo_markets:
            ticker, title, mkt_sport, _yes_price, _no_price, mkt_status, _volume = market

            # Sport filter
            if sport != "all" and mkt_sport.lower() != sport.lower():
                continue

            # Status filter
            if status != "all" and mkt_status.lower() != status.lower():
                continue

            # Search filter (case-insensitive search in ticker and title)
            if (
                search
                and search.lower() not in ticker.lower()
                and search.lower() not in title.lower()
            ):
                continue

            filtered_markets.append(market)

        # Apply pagination to filtered results
        total_filtered = len(filtered_markets)
        start = self._current_page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_markets = filtered_markets[start:end]

        # Add paginated rows to table
        for market in page_markets:
            table.add_row(*market)

        # Status message with filter info
        filter_parts = []
        if sport != "all":
            filter_parts.append(f"Sport: {sport.upper()}")
        if status != "all":
            filter_parts.append(f"Status: {status.title()}")
        if search:
            filter_parts.append(f'Search: "{search}"')

        filter_info = f" | Filters: {', '.join(filter_parts)}" if filter_parts else ""

        page_info = f"Page {self._current_page + 1}"
        has_more = end < total_filtered
        if has_more:
            page_info += " | [dim]n=Next[/]"
        if self._current_page > 0:
            page_info = "[dim]p=Prev[/] | " + page_info

        self.query_one("#market-status", Static).update(
            f"[bold yellow on #3D2A00]  SAMPLE DATA  [/] "
            f"[dim]Showing {len(page_markets)} of {total_filtered} demo markets{filter_info}[/] | {page_info}"
        )

    def _load_markets_from_api(
        self, table: DataTable, sport: str = "all", status: str = "all", search: str = ""
    ) -> bool:
        """Load markets directly from the Kalshi API with pagination.

        This method bypasses the database and fetches live market data
        directly from Kalshi's API endpoint. Uses pagination to fetch
        more than 100 markets.

        Args:
            table: The DataTable to populate
            sport: Sport filter (all, nfl, nba, etc.) - NOTE: Kalshi API doesn't filter by sport
            status: Status filter (all, open, closed, settled)
            search: Search term for ticker/title

        Returns:
            True if data was loaded successfully, False otherwise

        Educational Note:
            The Kalshi API limits responses to 200 markets max per request.
            We use cursor-based pagination to fetch multiple pages.
            The API uses series_ticker for sport filtering (e.g., KXNFLGAME).

        Reference:
            - KalshiClient.get_markets() for API implementation
            - API uses cursor for pagination
        """
        try:
            from precog.api_connectors.kalshi_client import KalshiClient

            # Get API environment from app (demo or production)
            api_env = self._get_api_environment()
            logger.debug(f"Loading markets from Kalshi API ({api_env} environment)")

            # Update status to show loading
            self.query_one("#market-status", Static).update(
                "[dim]Fetching markets from Kalshi API...[/]"
            )

            # Create client with current environment
            client = KalshiClient(environment=api_env)

            try:
                # Map sport filter to Kalshi series_ticker
                series_ticker = None
                if sport != "all":
                    sport_to_series = {
                        "nfl": "KXNFLGAME",
                        "nba": "KXNBAGAME",
                        "nhl": "KXNHLGAME",
                        "ncaaf": "KXNCAAFGAME",
                        "ncaab": "KXNCAABGAME",
                        "mlb": "KXMLBGAME",
                    }
                    series_ticker = sport_to_series.get(sport.lower())

                # Fetch up to 200 markets (API maximum per request)
                # Educational Note: For now we fetch one page of 200.
                # Full pagination would require modifying KalshiClient to
                # return the cursor along with markets.
                markets = client.get_markets(series_ticker=series_ticker, limit=200)

                if not markets:
                    logger.debug("No markets returned from API")
                    return False

                # Filter by status if specified
                if status != "all":
                    markets = [m for m in markets if m.get("status", "").lower() == status.lower()]

                # Filter by search term if specified
                if search:
                    search_lower = search.lower()
                    markets = [
                        m
                        for m in markets
                        if search_lower in m.get("ticker", "").lower()
                        or search_lower in m.get("title", "").lower()
                    ]

                # Add rows to table with proper text handling
                for market in markets:
                    # Extract sport from series_ticker (e.g., KXNFLGAME -> NFL)
                    series = market.get("series_ticker", "")
                    mkt_sport = self._extract_sport_from_series(series)

                    # Get prices (yes_ask and no_ask from API)
                    yes_price = market.get("yes_ask", Decimal("0"))
                    no_price = market.get("no_ask", Decimal("0"))

                    # Safely format prices
                    yes_str = self._format_price(yes_price)
                    no_str = self._format_price(no_price)

                    # Truncate and clean title for display
                    title = self._clean_text(market.get("title", ""), max_len=45)
                    ticker = self._clean_text(market.get("ticker", ""), max_len=30)

                    # Format volume safely (REST API uses _fp suffix for integer fields)
                    raw_vol = market.get("volume_fp")
                    volume = int(float(raw_vol)) if raw_vol else 0
                    volume_str = f"{int(volume):,}" if volume else "0"

                    table.add_row(
                        ticker,
                        title,
                        mkt_sport,
                        yes_str,
                        no_str,
                        market.get("status", "").title(),
                        volume_str,
                    )

                # Status message
                env_label = "DEMO API" if api_env == "demo" else "LIVE API"
                self.query_one("#market-status", Static).update(
                    f"[bold green on #1a3d1a]  {env_label}  [/] "
                    f"Loaded {len(markets)} markets from Kalshi"
                )

                logger.info(f"Loaded {len(markets)} markets from Kalshi {api_env} API")
                return True

            finally:
                # Always close the client to cleanup resources
                client.close()

        except ImportError as e:
            logger.debug(f"Kalshi client not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to load markets from API: {e}")
            self.query_one("#market-status", Static).update(f"[red]API Error: {str(e)[:50]}[/]")
            return False

    def _extract_sport_from_series(self, series_ticker: str) -> str:
        """Extract sport name from series ticker.

        Args:
            series_ticker: Kalshi series ticker (e.g., KXNFLGAME)

        Returns:
            Sport abbreviation (NFL, NBA, etc.) or "OTHER"
        """
        series_upper = series_ticker.upper()
        if "NFL" in series_upper:
            return "NFL"
        if "NBA" in series_upper:
            return "NBA"
        if "NHL" in series_upper:
            return "NHL"
        if "NCAAF" in series_upper:
            return "NCAAF"
        if "NCAAB" in series_upper:
            return "NCAAB"
        if "MLB" in series_upper:
            return "MLB"
        return "OTHER"

    def _format_price(self, price) -> str:
        """Safely format a price as dollar string.

        Args:
            price: Price value (Decimal, float, int, or None)

        Returns:
            Formatted price string like "$0.55"
        """
        try:
            if isinstance(price, Decimal):
                return f"${price:.2f}"
            if price is None:
                return "$0.00"
            return f"${Decimal(str(price)):.2f}"
        except (ValueError, TypeError):
            return "$0.00"

    def _clean_text(self, text: str, max_len: int = 50) -> str:
        """Clean and truncate text for display.

        Removes ANSI codes, control characters, and truncates to max length.

        Args:
            text: Input text
            max_len: Maximum length before truncation

        Returns:
            Clean, truncated text
        """
        if not text:
            return ""
        # Remove any ANSI escape codes or control characters
        import re

        clean = re.sub(r"\x1b\[[0-9;]*m", "", str(text))
        clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", clean)
        # Truncate if needed
        if len(clean) > max_len:
            return clean[: max_len - 3] + "..."
        return clean

    def on_select_changed(self, event: Select.Changed) -> None:  # noqa: ARG002
        """Handle filter dropdown changes."""
        self._apply_filters()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        # Debounce would be nice here, but for simplicity we refresh immediately
        if event.input.id == "search-input":
            self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filter values to reload markets.

        Educational Note:
            Resets to page 0 when filters change, since the result set
            is different and the current page offset may be invalid.
        """
        self._current_page = 0
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

    def action_next_page(self) -> None:
        """Navigate to the next page of results."""
        table = self.query_one("#market-table", DataTable)
        if table.row_count < self.PAGE_SIZE:
            self.app.notify("Already on last page")
            return
        self._current_page += 1
        sport = self.query_one("#sport-filter", Select).value
        status = self.query_one("#status-filter", Select).value
        search = self.query_one("#search-input", Input).value
        self._load_markets(
            sport=str(sport) if sport else "all",
            status=str(status) if status else "all",
            search=search,
        )

    def action_prev_page(self) -> None:
        """Navigate to the previous page of results."""
        if self._current_page > 0:
            self._current_page -= 1
            sport = self.query_one("#sport-filter", Select).value
            status = self.query_one("#status-filter", Select).value
            search = self.query_one("#search-input", Input).value
            self._load_markets(
                sport=str(sport) if sport else "all",
                status=str(status) if status else "all",
                search=search,
            )

    def action_focus_filter(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-fetch-api":
            self.action_fetch_from_api()

    def action_fetch_from_api(self) -> None:
        """Fetch markets directly from Kalshi API.

        This bypasses the database and fetches live data from the Kalshi API.
        Useful when the scheduler pollers aren't running or the database
        isn't populated.

        Educational Note:
            This provides an "escape hatch" when the normal data flow
            (Kalshi API → Poller → Database → TUI) is broken. Users can
            get live data without needing to start background pollers.
        """
        table = self.query_one("#market-table", DataTable)
        table.clear()

        # Get current filter values
        sport = self.query_one("#sport-filter", Select).value
        status = self.query_one("#status-filter", Select).value
        search = self.query_one("#search-input", Input).value

        sport_str = str(sport) if sport else "all"
        status_str = str(status) if status else "all"

        # Try to load from API
        success = self._load_markets_from_api(
            table, sport=sport_str, status=status_str, search=search
        )

        if success:
            self.app.notify("Loaded markets from Kalshi API")
        else:
            self.app.notify("Failed to fetch from API - check credentials", severity="error")
            # Fall back to demo data
            self._load_demo_data(table, sport=sport_str, status=status_str, search=search)
