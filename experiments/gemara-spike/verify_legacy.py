#!/usr/bin/env python3
"""Run Attempt 1's mocked unit tests with all real processes/network disabled."""

from pathlib import Path
import socket
import subprocess
import unittest


def main() -> int:
    attempts = []

    def deny(*args, **kwargs):
        attempts.append("blocked external operation")
        raise RuntimeError("External process/network disabled during legacy unit tests")

    socket.create_connection = deny
    socket.socket.connect = deny
    subprocess.Popen = deny
    root = Path(__file__).resolve().parents[2]
    suite = unittest.TestLoader().discover(
        str(root / "tests"), pattern="test_auto_merge.py"
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if attempts:
        raise SystemExit("Legacy tests attempted an unmocked external operation.")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
