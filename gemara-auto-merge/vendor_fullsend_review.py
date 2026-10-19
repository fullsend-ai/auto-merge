#!/usr/bin/env python3
"""Compatibility entry point for refreshing the post-script host lock.

The historical binary export is retired. Its source remains in Git history.
"""

import sys

from configure_review_postscript import configure


if __name__ == "__main__":
    if sys.argv[1:] != ["--lock"]:
        raise SystemExit("Binary export retired; use configure_review_postscript.py.")
    configure()
