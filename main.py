#!/usr/bin/env python3
"""
Polymarket Copy Trading Bot
Terminal-based trading bot with beautiful TUI.

Usage:
    python main.py

Keyboard shortcuts:
    S - Start/Stop bot
    C - Clear logs
    R - Refresh UI
    Q - Quit
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui import run


if __name__ == "__main__":
    run()
