#!/usr/bin/env python3
"""Adoption engine entry point.

    scripts/adoption/adoption.py plan
    scripts/adoption/adoption.py plan --check
    scripts/adoption/adoption.py graph --format mermaid
    scripts/adoption/adoption.py diff --before a.json --after b.json
    scripts/adoption/adoption.py catalog pin

Stdout is one canonical JSON document; logs and error prose go to stderr.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))

from cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
