"""Testy wyznaczania sciezki pliku wyjsciowego."""

from __future__ import annotations

from pathlib import Path

from epuap_auto_sign.signer import _determine_output_path


def test_pdf_keeps_pdf_extension(tmp_path: Path):
    """Plik PDF zostaje PDF, sufiks _signed."""
    pdf = tmp_path / "document.pdf"
    pdf.touch()
    result = _determine_output_path(pdf, None)
    assert result.name == "document_signed.pdf"
    assert result.parent == tmp_path.resolve()


def test_custom_output_path(tmp_path: Path):
    """Z podanym output_path, wynik to ten path."""
    pdf = tmp_path / "doc.pdf"
    output = tmp_path / "custom.pdf"
    result = _determine_output_path(pdf, output)
    assert result == output.resolve()


def test_non_pdf_extension_preserved(tmp_path: Path):
    """Rozszerzenie inne niz PDF tez jest zachowane."""
    doc = tmp_path / "doc.docx"
    doc.touch()
    result = _determine_output_path(doc, None)
    assert result.name == "doc_signed.docx"
