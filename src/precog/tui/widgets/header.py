"""
ASCII Art Header Widget.

Displays the PRECOG logo in ACiD BBS-inspired ASCII art style.
Uses block characters and gradient shading for depth.

Style Influences:
    - ACiD (ANSI Creators in Demand) - 1980s-90s BBS art group
    - Classic ANSI art with block character shading
    - Sci-fi terminal aesthetics

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
"""

from textual.widgets import Static

# ACiD-inspired ASCII art logo using block characters
# Uses gradient shading: ░▒▓█ for depth effect
PRECOG_LOGO = r"""
[cyan]
    ██████╗ ██████╗ ███████╗ ██████╗ ██████╗  ██████╗
    ██╔══██╗██╔══██╗██╔════╝██╔════╝██╔═══██╗██╔════╝
    ██████╔╝██████╔╝█████╗  ██║     ██║   ██║██║  ███╗
    ██╔═══╝ ██╔══██╗██╔══╝  ██║     ██║   ██║██║   ██║
    ██║     ██║  ██║███████╗╚██████╗╚██████╔╝╚██████╔╝
    ╚═╝     ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝
[/cyan]
[dim]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/dim]
[bold white]          P R E D I C T I O N   M A R K E T   I N T E L L I G E N C E[/bold white]
[dim]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/dim]
"""

# Compact logo for smaller terminals
PRECOG_LOGO_COMPACT = r"""
[cyan]╔═══════════════════════════════════════════════╗
║[bold white]  PRECOG [/bold white][dim]- Prediction Market Intelligence[/dim]   ║
╚═══════════════════════════════════════════════╝[/cyan]
"""


class AsciiHeader(Static):
    """
    ASCII art header displaying the PRECOG logo.

    Automatically switches between full and compact logos
    based on terminal width.

    Attributes:
        DEFAULT_CSS: Styling for the header widget
    """

    DEFAULT_CSS = """
    AsciiHeader {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding: 1 0;
    }
    """

    def __init__(self) -> None:
        """Initialize the ASCII header with the full logo."""
        super().__init__(PRECOG_LOGO, id="ascii-header")

    def on_resize(self) -> None:
        """Switch between full and compact logo based on terminal width."""
        if self.size.width < 70:
            self.update(PRECOG_LOGO_COMPACT)
        else:
            self.update(PRECOG_LOGO)
