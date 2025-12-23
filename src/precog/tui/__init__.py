"""
Precog Terminal User Interface (TUI).

A full-featured terminal interface built with Textual, featuring a sci-fi aesthetic
inspired by Philip K. Dick, Frank Herbert, William Gibson, Dan Simmons, and
James S.A. Corey. ASCII art influenced by classic BBS groups like ACiD.

Usage:
    python main.py tui              # Launch TUI with default theme
    python main.py tui --theme=acid # Launch with ACiD BBS theme
    python -m precog.tui            # Direct module launch

Reference:
    - Issue #268: Textual-based Sci-Fi Terminal UI
    - Textual docs: https://textual.textualize.io/

Themes Available:
    - precog_dark (default): Sci-fi dark theme with subtle references
    - precog_classic: Clean, minimal, no thematic elements
    - precog_acid: Full ACiD BBS aesthetic
    - precog_cyberpunk: Neon-heavy Gibson-inspired variant
"""

from precog.tui.app import PrecogApp

__all__ = ["PrecogApp"]
