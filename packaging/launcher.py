"""PyInstaller entry point (a script, not ``-m``, so imports are absolute)."""

import sys

from colorize.app import main

sys.exit(main())
