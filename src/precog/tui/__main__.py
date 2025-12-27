"""Entry point for running TUI as a module.

Usage:
    python -m precog.tui

This enables the TUI to be launched directly without going through the CLI.
"""

from precog.tui.app import PrecogApp


def main() -> None:
    """Launch the Precog TUI application."""
    app = PrecogApp()
    app.run()


if __name__ == "__main__":
    main()
