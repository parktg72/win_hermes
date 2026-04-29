from pathlib import Path


def test_bat_eol_rule_exists():
    lines = Path(".gitattributes").read_text().splitlines()
    assert any("*.bat" in line and "eol=crlf" in line for line in lines)


def test_cmd_eol_rule_exists():
    lines = Path(".gitattributes").read_text().splitlines()
    assert any("*.cmd" in line and "eol=crlf" in line for line in lines)


def test_ps1_eol_rule_exists():
    lines = Path(".gitattributes").read_text().splitlines()
    assert any("*.ps1" in line and "eol=crlf" in line for line in lines)
