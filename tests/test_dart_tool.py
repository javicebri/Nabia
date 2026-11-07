import pytest

from tools.dart import FileCoverage, main, parse_lcov, render_coverage

LCOV = """\
SF:C:\\repo\\dart\\lib\\src\\a.dart
DA:1,3
DA:2,0
DA:4,1
LF:3
LH:2
end_of_record
SF:C:\\repo\\dart\\lib\\src\\b.dart
DA:7,2
end_of_record
"""


def test_parse_lcov() -> None:
    assert parse_lcov(LCOV) == [
        FileCoverage("C:\\repo\\dart\\lib\\src\\a.dart", 3, (2,)),
        FileCoverage("C:\\repo\\dart\\lib\\src\\b.dart", 1, ()),
    ]


def test_render_coverage() -> None:
    report = render_coverage(parse_lcov(LCOV))
    assert report == "a.dart: missed 2\nTOTAL 3/4 lines (75.0%)\n"
    assert render_coverage([]) == "TOTAL 0/0 lines (100.0%)\n"


def test_main_rejects_unknown_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["deploy"]) == 2
    assert "usage" in capsys.readouterr().err


def test_main_needs_the_sdk(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("tools.dart.shutil.which", lambda _: None)
    assert main([]) == 1
    assert "Dart SDK" in capsys.readouterr().err
