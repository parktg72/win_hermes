from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_main_tests_workflow_uses_python_312():
    workflow = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "uv python install 3.12" in workflow
    assert "uv venv .venv --python 3.12" in workflow
    assert "uv python install 3.11" not in workflow


def test_windows_smoke_workflow_exists_and_checks_release_builder():
    workflow = REPO_ROOT / ".github" / "workflows" / "windows-smoke.yml"
    body = workflow.read_text()
    assert "windows-latest" in body
    assert "python-version: '3.12'" in body
    assert "python -m venv .venv" in body
    assert "scripts/build_windows_release.py --check-only" in body
    assert "tests/test_windows_release_builder.py" in body
    assert "tests/test_windows_release_workflows.py" in body
    smoke_command = body.split("Run Windows release smoke tests", maxsplit=1)[1]
    assert "tests/test_ollama" not in smoke_command
