# tests/test_gitattributes.py
from pathlib import Path

def test_bat_eol_rule_exists():
    content = Path(".gitattributes").read_text()
    assert "*.bat" in content and "eol=crlf" in content

def test_cmd_eol_rule_exists():
    content = Path(".gitattributes").read_text()
    assert "*.cmd" in content and "eol=crlf" in content

def test_ps1_eol_rule_exists():
    content = Path(".gitattributes").read_text()
    assert "*.ps1" in content and "eol=crlf" in content
