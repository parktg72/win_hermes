"""Tests for the top-level error guard wrapping main()."""
from pathlib import Path
from unittest.mock import patch

import pytest


def test_run_main_propagates_systemexit():
    """SystemExit (sys.exit(N)) must propagate untouched — main() uses it."""
    from hermes_cli.main import _run_main
    with patch("hermes_cli.main.main", side_effect=SystemExit(2)):
        with pytest.raises(SystemExit) as excinfo:
            _run_main()
        assert excinfo.value.code == 2


def test_run_main_keyboard_interrupt_exits_130():
    """Ctrl+C exits with conventional code 130, no traceback."""
    from hermes_cli.main import _run_main
    with patch("hermes_cli.main.main", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as excinfo:
            _run_main()
        assert excinfo.value.code == 130


def test_run_main_unexpected_exception_exits_1_with_korean(capsys, tmp_path):
    """Any unexpected exception → Korean stderr + exit(1) + log file written."""
    from hermes_cli.main import _run_main, _log_unexpected_error

    with patch("hermes_cli.main.main", side_effect=RuntimeError("boom")):
        with patch("hermes_cli.main._log_unexpected_error") as mock_log:
            with pytest.raises(SystemExit) as excinfo:
                _run_main()
            assert excinfo.value.code == 1
            mock_log.assert_called_once()


def test_log_unexpected_error_writes_korean_stderr_and_log(capsys, tmp_path):
    from hermes_cli.main import _log_unexpected_error

    exc = RuntimeError("boom")
    _log_unexpected_error(exc, log_dir=tmp_path)

    captured = capsys.readouterr()
    assert "오류" in captured.err
    assert "RuntimeError" in captured.err

    log_path = tmp_path / "error.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "RuntimeError" in content
    assert "boom" in content


def test_log_unexpected_error_handles_unwritable_log_dir(capsys, tmp_path):
    """If log dir cannot be written, stderr message still appears (no double-fail)."""
    from hermes_cli.main import _log_unexpected_error

    bogus = tmp_path / "does_not_exist_and_cannot_create" / "x" / "y"
    with patch("pathlib.Path.mkdir", side_effect=OSError("no perms")):
        _log_unexpected_error(RuntimeError("boom"), log_dir=bogus)

    captured = capsys.readouterr()
    assert "오류" in captured.err
