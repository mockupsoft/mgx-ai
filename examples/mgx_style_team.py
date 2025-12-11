# -*- coding: utf-8 -*-
"""
MGX Style Multi-Agent Team - Example Wrapper

This is a simple wrapper around the modularized mgx_agent package.
For implementation details, see: /mgx_agent/
"""

import os
import sys

# Setup path for imports
CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import from modularized package
from mgx_agent.cli import cli_main, main, incremental_main
from mgx_agent import (
    MGXStyleTeam,
    TeamConfig,
    TaskComplexity,
)

__all__ = [
    'MGXStyleTeam',
    'TeamConfig',
    'TaskComplexity',
    'main',
    'incremental_main',
]

if __name__ == "__main__":
    cli_main()
