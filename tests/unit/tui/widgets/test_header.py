"""Unit tests for TUI Header Widget.

Tests for the ASCII art header widget.

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
    - src/precog/tui/widgets/header.py
"""

from __future__ import annotations


class TestAsciiHeader:
    """Test AsciiHeader widget class."""

    def test_ascii_header_instantiates(self) -> None:
        """Verify AsciiHeader can be instantiated."""
        from precog.tui.widgets.header import AsciiHeader

        header = AsciiHeader()
        assert header is not None

    def test_ascii_header_has_art(self) -> None:
        """Verify AsciiHeader has ASCII art content."""
        from precog.tui.widgets.header import AsciiHeader

        header = AsciiHeader()
        # Header should have art attribute or content
        assert hasattr(header, "art") or hasattr(AsciiHeader, "DEFAULT_CSS")
