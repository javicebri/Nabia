"""Run the Dart package checks from the repository root.

Used by the ``dart`` pre-commit hook; equivalent to running, inside
``dart/``: ``dart pub get``, ``dart format --set-exit-if-changed``,
``dart analyze --fatal-infos``, ``dart run tool/generate.dart --check``
and ``dart test``::

    uv run python -m tools.dart
"""

import shutil
import subprocess
import sys
from pathlib import Path

#: Root of the Dart package.
DART_DIR = Path(__file__).resolve().parent.parent / "dart"

#: Checks, in order; the first failure stops the run.
STEPS: tuple[tuple[str, ...], ...] = (
    ("pub", "get"),
    ("format", "--output=none", "--set-exit-if-changed", "."),
    ("analyze", "--fatal-infos"),
    ("run", "tool/generate.dart", "--check"),
    ("test",),
)


def main() -> int:
    """Run every step; return the exit status of the first failure."""
    dart = shutil.which("dart")
    if dart is None:
        sys.stderr.write("Dart SDK not found in PATH\n")
        return 1
    for step in STEPS:
        # Fixed arguments and an executable resolved from PATH.
        result = subprocess.run(  # noqa: S603
            [dart, *step], cwd=DART_DIR, check=False
        )
        if result.returncode != 0:
            sys.stderr.write(f"dart {' '.join(step)} failed\n")
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
