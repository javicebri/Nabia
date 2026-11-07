"""Run the Dart package checks from the repository root.

``check`` (the default, also the ``dart`` pre-commit hook) runs, inside
``dart/``: ``dart pub get``, ``dart format --set-exit-if-changed``,
``dart analyze --fatal-infos``, ``dart run tool/generate.dart --check``
and ``dart test``. ``coverage`` runs the tests with coverage and prints
the uncovered lines of ``lib/``::

    uv run python -m tools.dart [check | coverage]
"""

import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

#: Root of the Dart package.
DART_DIR = Path(__file__).resolve().parent.parent / "dart"

#: Checks, in order; the first failure stops the run.
CHECK_STEPS: tuple[tuple[str, ...], ...] = (
    ("pub", "get"),
    ("format", "--output=none", "--set-exit-if-changed", "."),
    ("analyze", "--fatal-infos"),
    ("run", "tool/generate.dart", "--check"),
    ("test",),
)

#: Tests with coverage; writes ``coverage/lcov.info``.
COVERAGE_STEPS: tuple[tuple[str, ...], ...] = (
    ("pub", "get"),
    ("run", "coverage:test_with_coverage"),
)


@dataclass(frozen=True)
class FileCoverage:
    """Line coverage of one source file."""

    path: str
    lines: int
    missed: tuple[int, ...]


def parse_lcov(text: str) -> list[FileCoverage]:
    """Return the line coverage of every file in an lcov report."""
    files: list[FileCoverage] = []
    path: str | None = None
    hits: dict[int, int] = {}
    for line in text.splitlines():
        if line.startswith("SF:"):
            path, hits = line[3:], {}
        elif line.startswith("DA:") and path is not None:
            number, count = line[3:].split(",")[:2]
            hits[int(number)] = int(count)
        elif line == "end_of_record" and path is not None:
            missed = tuple(n for n, count in sorted(hits.items()) if not count)
            files.append(FileCoverage(path, len(hits), missed))
            path = None
    return files


def render_coverage(files: Sequence[FileCoverage]) -> str:
    """Render a summary: uncovered lines per file, then the total."""
    lines = [
        f"{Path(f.path).name}: missed {', '.join(map(str, f.missed))}"
        for f in files
        if f.missed
    ]
    total = sum(f.lines for f in files)
    covered = total - sum(len(f.missed) for f in files)
    percent = 100.0 * covered / total if total else 100.0
    lines.append(f"TOTAL {covered}/{total} lines ({percent:.1f}%)")
    return "\n".join(lines) + "\n"


def _run(dart: str, steps: Sequence[tuple[str, ...]]) -> int:
    for step in steps:
        # Fixed arguments and an executable resolved from PATH.
        result = subprocess.run(  # noqa: S603
            [dart, *step], cwd=DART_DIR, check=False
        )
        if result.returncode != 0:
            sys.stderr.write(f"dart {' '.join(step)} failed\n")
            return result.returncode
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested command; return the process exit status."""
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "check"
    if command not in ("check", "coverage") or len(args) > 1:
        sys.stderr.write("usage: python -m tools.dart [check | coverage]\n")
        return 2
    dart = shutil.which("dart")
    if dart is None:
        sys.stderr.write("Dart SDK not found in PATH\n")
        return 1
    if command == "check":
        return _run(dart, CHECK_STEPS)
    status = _run(dart, COVERAGE_STEPS)
    if status == 0:
        report = DART_DIR / "coverage" / "lcov.info"
        files = parse_lcov(report.read_text(encoding="utf-8"))
        sys.stdout.write(render_coverage(files))
    return status


if __name__ == "__main__":
    sys.exit(main())
