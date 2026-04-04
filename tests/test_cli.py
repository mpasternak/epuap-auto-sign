"""Testy CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from epuap_auto_sign.cli import build_parser, main


def test_parser_requires_pdf():
    """CLI wymaga argumentu z plikiem PDF."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_basic(tmp_path: Path):
    """Parsowanie podstawowych argumentow."""
    parser = build_parser()
    args = parser.parse_args(["document.pdf"])
    assert args.pdf == Path("document.pdf")
    assert args.output is None
    assert args.timeout == 300
    assert args.method == "Profil zaufany"
    assert args.sig_x == 50.0
    assert args.sig_y == 66.0
    assert args.verbose is False


def test_parser_full(tmp_path: Path):
    """Parsowanie wszystkich opcji."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "doc.pdf",
            "-o",
            "out.pdf",
            "-t",
            "600",
            "-c",
            "/etc/config.toml",
            "-m",
            "Certyfikat kwalifikowany",
            "-x",
            "30",
            "-y",
            "80",
            "-v",
        ]
    )
    assert args.pdf == Path("doc.pdf")
    assert args.output == Path("out.pdf")
    assert args.timeout == 600
    assert args.config == Path("/etc/config.toml")
    assert args.method == "Certyfikat kwalifikowany"
    assert args.sig_x == 30.0
    assert args.sig_y == 80.0
    assert args.verbose is True


def test_main_missing_file(capsys, tmp_path: Path):
    """Brak pliku zwraca kod bledu 1."""
    missing = tmp_path / "nonexistent.pdf"
    result = main([str(missing)])
    assert result == 1
    captured = capsys.readouterr()
    assert "nie istnieje" in captured.err.lower()
