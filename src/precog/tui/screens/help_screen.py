"""
Help Screen.

Comprehensive documentation and keyboard shortcut reference.
Provides in-app documentation for all TUI features.

Design:
    - Tabbed interface for different help sections
    - Keyboard shortcuts reference
    - Screen-by-screen documentation
    - Quick tips for new users

Reference:
    - Issue #286: TUI Help and Documentation
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Markdown, Static, TabbedContent, TabPane

from precog.tui.screens.base_screen import BaseScreen
from precog.tui.widgets.breadcrumb import Breadcrumb
from precog.tui.widgets.environment_bar import EnvironmentBar

# Help content organized by section
QUICK_START_HELP = """
# Quick Start Guide

Welcome to **PRECOG** - Prediction Market Intelligence System!

## Getting Started

1. **Navigate** using number keys (1-8) or arrow keys
2. **Press Enter** to select a menu item
3. **Press Escape** to go back to the previous screen
4. **Press Q** to quit the application

## Main Menu Options

| Key | Screen | Description |
|-----|--------|-------------|
| 1 | Market Overview | Browse live market prices and edge calculations |
| 2 | Positions | View current positions and P&L |
| 3 | Execute Trades | Order entry and trade execution (coming soon) |
| 4 | Scheduler | Control ESPN and Kalshi pollers |
| 5 | Strategy Manager | Create and manage trading strategies (coming soon) |
| 6 | Model Manager | ML models and predictions (coming soon) |
| 7 | Configuration | System settings and connections |
| 8 | Diagnostics | Logs, health checks, and debugging |

## Understanding Sample Data

When you see **[SAMPLE DATA]** in yellow, the displayed information is
demonstration data only - not real market prices or positions. This occurs
when the database is unavailable or the system is in demo mode.

Real data will show **[LIVE]** or no indicator at all.
"""

KEYBOARD_SHORTCUTS_HELP = """
# Keyboard Shortcuts

## Global Shortcuts (work everywhere)

| Key | Action |
|-----|--------|
| Q | Quit application |
| Escape | Go back to previous screen |
| Ctrl+T | Cycle through themes |
| ? | Open this help screen |
| Tab | Focus next element |
| Shift+Tab | Focus previous element |

## Navigation

| Key | Action |
|-----|--------|
| Arrow Up/Down | Move focus up/down |
| Arrow Left/Right | Move focus left/right |
| J/K | Vim-style up/down navigation |
| Enter | Select focused item |
| 1-8 | Quick navigate to menu items |

## Screen-Specific Shortcuts

### Market Browser
| Key | Action |
|-----|--------|
| R | Refresh market data |
| F | Focus search filter |

### Position Viewer
| Key | Action |
|-----|--------|
| R | Refresh positions |
| O | Show open positions only |
| A | Show all positions |

### Monitoring Dashboard
| Key | Action |
|-----|--------|
| R | Manual refresh |
| L | Toggle log panel |

### Scheduler Control
| Key | Action |
|-----|--------|
| R | Refresh services |
| S | Start all services |
| X | Stop all services |
| L | Toggle log panel |

### Settings
| Key | Action |
|-----|--------|
| R | Refresh configuration |
| T | Test all connections |
"""

THEMES_HELP = """
# Themes

PRECOG includes four visual themes. Press **Ctrl+T** to cycle through them:

## Available Themes

### 1. Dark (Default)
- **Style:** Blade Runner inspired
- **Colors:** Cyan primary, Amber accent, Deep Navy background
- **Best for:** Extended use, low-light environments

### 2. Classic
- **Style:** Retro terminal, IBM mainframe
- **Colors:** Green on black, high contrast
- **Best for:** Nostalgia, maximum readability

### 3. ACiD
- **Style:** 90s BBS ANSI art
- **Colors:** Hot Pink, Electric Blue, Deep Purple
- **Best for:** Standing out, creative environments

### 4. Cyberpunk
- **Style:** Neon dystopian future
- **Colors:** Neon Yellow, Hot Magenta, Pure Black
- **Best for:** Night coding, immersive experience

## Theme Persistence

Theme selection is currently session-only. Your theme choice will reset
to "Dark" when you restart the application. Persistent theme storage
is planned for a future release.
"""

SCREENS_HELP = """
# Screen Reference

## Market Browser (Key: 1)

View and filter Kalshi prediction markets.

**Features:**
- Filter by sport (NFL, NBA, NHL, NCAAF, NCAAB, MLB)
- Filter by status (Open, Closed, Settled)
- Search by ticker or title
- View market details on selection

**Columns:**
- Ticker: Unique market identifier
- Title: Market question
- Sport: Sport category
- Yes/No Price: Current contract prices ($0.00-$1.00)
- Status: Market state
- Volume: Trading volume

---

## Position Viewer (Key: 2)

Monitor your trading positions and P&L.

**Summary Panel:**
- Open Positions: Count of active positions
- Unrealized P&L: Profit/loss on open positions
- Realized P&L: Profit/loss from closed positions
- Total P&L: Combined profit/loss

**Position Details:**
- Position ID, Market, Side (YES/NO)
- Quantity, Entry Price, Current Price
- P&L ($), P&L (%), Status

---

## Scheduler Control (Key: 4)

Manage background polling services.

**Services:**
- ESPN Game Poller: Fetches live game data
- ESPN Rankings Poller: Fetches team rankings/Elo
- Kalshi Market Poller: Fetches market prices
- Position Monitor: Watches open positions
- Alert Dispatcher: Sends notifications

**Controls:**
- Start/Stop/Restart individual services
- View service logs and errors

---

## Monitoring Dashboard (Key: 8)

Real-time system health monitoring.

**Health Cards:**
- Database connection status
- API rate limit usage
- Service health indicators

**Metrics:**
- Error rate trends (sparkline)
- API response times (sparkline)
- Detailed metrics table

**Live Logs:**
- Real-time event stream
- Color-coded by severity
"""

TROUBLESHOOTING_HELP = """
# Troubleshooting

## Common Issues

### "SAMPLE DATA" Warning
**Problem:** Seeing [SAMPLE DATA] indicator

**Cause:** Database connection unavailable or in demo mode

**Solution:**
1. Check database is running: `pg_isready`
2. Verify connection settings in Settings screen (Key: 7)
3. Test connection using "Test Database" button

---

### Theme Not Changing
**Problem:** Ctrl+T doesn't change theme

**Cause:** Theme CSS file missing or corrupted

**Solution:**
1. Check `src/precog/tui/styles/` for .tcss files
2. Verify all 4 theme files exist
3. Restart the application

---

### Screen Not Responding
**Problem:** Keyboard input not working

**Cause:** Focus may be on a different widget

**Solution:**
1. Press Tab to cycle focus
2. Press Escape to return to main menu
3. Press Q and restart if unresponsive

---

### High CPU Usage
**Problem:** TUI using excessive CPU

**Cause:** Rapid refresh intervals or live updates

**Solution:**
1. Go to Settings (Key: 7)
2. Disable "Auto-Refresh"
3. Use manual refresh (R) instead

---

## Getting Help

- **In-app:** Press ? for this help screen
- **Documentation:** See docs/guides/ folder
- **Issues:** https://github.com/anthropics/precog/issues

## Reporting Bugs

When reporting issues, please include:
1. Theme in use (see status bar)
2. Screen where issue occurred
3. Exact error message if any
4. Steps to reproduce
"""


class HelpScreen(BaseScreen):
    """
    Comprehensive help screen with tabbed documentation.

    Provides in-app documentation for all TUI features,
    keyboard shortcuts, and troubleshooting guidance.

    Educational Note:
        This screen uses Textual's TabbedContent widget for
        organizing help sections. The Markdown widget renders
        documentation with proper formatting (headers, tables,
        code blocks) from plain text strings.
        Inherits from BaseScreen but overrides 'q' to close help
        instead of quitting the app.
    """

    # Override the global 'q' binding to close help instead of quitting
    # We start fresh rather than extending to avoid duplicate bindings
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("q", "go_back", "Close", show=True),  # Close help, not quit app
        Binding("?", "show_help", "Help", show=False),  # Already on help screen
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Create the help screen layout."""
        yield Breadcrumb.for_screen("help_screen")
        yield EnvironmentBar.from_app(self.app)
        yield Label(
            "[bold cyan]PRECOG Help & Documentation[/]",
            id="help-title",
            classes="screen-title",
        )

        with TabbedContent():
            with TabPane("Quick Start", id="tab-quickstart"):
                with VerticalScroll():
                    yield Markdown(QUICK_START_HELP)

            with TabPane("Keyboard", id="tab-keyboard"):
                with VerticalScroll():
                    yield Markdown(KEYBOARD_SHORTCUTS_HELP)

            with TabPane("Themes", id="tab-themes"):
                with VerticalScroll():
                    yield Markdown(THEMES_HELP)

            with TabPane("Screens", id="tab-screens"):
                with VerticalScroll():
                    yield Markdown(SCREENS_HELP)

            with TabPane("Troubleshooting", id="tab-trouble"):
                with VerticalScroll():
                    yield Markdown(TROUBLESHOOTING_HELP)

        # Footer with navigation hints
        with Horizontal(id="help-footer"):
            yield Static("[dim]Tab/Arrow keys to navigate sections[/]")
            yield Static("[dim]Escape or Q to close[/]")

    def action_go_back(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()
