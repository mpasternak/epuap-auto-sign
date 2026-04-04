"""Testy modulu config."""

from __future__ import annotations

from pathlib import Path

import pytest

from epuap_auto_sign.config import (
    find_signature_position,
    get_signature_position,
    load_config,
    load_credentials,
    resolve_config_path,
    save_signature_position,
)


def test_resolve_config_path_default():
    """Bez argumentu zwraca domyslna sciezke."""
    assert resolve_config_path() == Path("config.toml")


def test_resolve_config_path_custom(tmp_path: Path):
    """Z argumentem zwraca przekazana sciezke."""
    custom = tmp_path / "my_config.toml"
    assert resolve_config_path(custom) == custom


def test_load_config_missing_file(tmp_path: Path):
    """Brak pliku zwraca pusty dict."""
    missing = tmp_path / "nonexistent.toml"
    assert load_config(missing) == {}


def test_load_config_valid(tmp_path: Path):
    """Wczytuje poprawny plik TOML."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[credentials]\nusername = "jan"\npassword = "tajne"\n',
        encoding="utf-8",
    )
    result = load_config(config_file)
    assert result == {"credentials": {"username": "jan", "password": "tajne"}}


def test_load_credentials_complete():
    """Kompletne dane zwracane sa jako dict."""
    config = {"credentials": {"username": "jan", "password": "tajne"}}
    assert load_credentials(config) == {"username": "jan", "password": "tajne"}


def test_load_credentials_missing_username():
    """Brak username zwraca None."""
    config = {"credentials": {"password": "tajne"}}
    assert load_credentials(config) is None


def test_load_credentials_missing_password():
    """Brak password zwraca None."""
    config = {"credentials": {"username": "jan"}}
    assert load_credentials(config) is None


def test_load_credentials_empty_config():
    """Pusta konfiguracja zwraca None."""
    assert load_credentials({}) is None


def test_load_credentials_empty_values():
    """Puste wartosci traktowane sa jak brak."""
    config = {"credentials": {"username": "", "password": "tajne"}}
    assert load_credentials(config) is None


class TestFindSignaturePosition:
    def test_no_signatures_section(self):
        """Brak sekcji [signatures] zwraca None."""
        assert find_signature_position({}, Path("/tmp/doc.pdf")) is None

    def test_exact_match(self):
        """Dopasowanie pelna sciezka."""
        config = {
            "signatures": {
                "/tmp/doc.pdf": {"x": 30, "y": 70},
            }
        }
        assert find_signature_position(config, Path("/tmp/doc.pdf")) == (30.0, 70.0)

    def test_glob_match(self):
        """Dopasowanie wzorca glob."""
        config = {
            "signatures": {
                "/tmp/*.pdf": {"x": 40, "y": 80},
            }
        }
        assert find_signature_position(config, Path("/tmp/doc.pdf")) == (40.0, 80.0)

    def test_first_match_wins(self):
        """Pierwszy pasujacy wzorzec wygrywa."""
        config = {
            "signatures": {
                "/tmp/doc.pdf": {"x": 10, "y": 10},
                "/tmp/*.pdf": {"x": 20, "y": 20},
            }
        }
        assert find_signature_position(config, Path("/tmp/doc.pdf")) == (10.0, 10.0)

    def test_no_match(self):
        """Brak dopasowania zwraca None."""
        config = {
            "signatures": {
                "/other/*.pdf": {"x": 10, "y": 10},
            }
        }
        assert find_signature_position(config, Path("/tmp/doc.pdf")) is None

    def test_default_values_when_missing_xy(self):
        """Brak x/y uzywa wartosci domyslnych."""
        config = {
            "signatures": {
                "/tmp/doc.pdf": {},
            }
        }
        assert find_signature_position(config, Path("/tmp/doc.pdf")) == (50.0, 66.0)


class TestGetSignaturePosition:
    def test_matched_wins(self):
        """Dopasowanie w [signatures] ma priorytet."""
        config = {
            "signatures": {"/tmp/doc.pdf": {"x": 10, "y": 20}},
            "signature": {"x": 90, "y": 90},
        }
        assert get_signature_position(config, Path("/tmp/doc.pdf"), 50, 50) == (10.0, 20.0)

    def test_fallback_to_global(self):
        """Brak dopasowania -> uzywa [signature]."""
        config = {"signature": {"x": 30, "y": 40}}
        assert get_signature_position(config, Path("/tmp/doc.pdf"), 50, 50) == (30.0, 40.0)

    def test_fallback_to_defaults(self):
        """Brak konfiguracji -> uzywa wartosci domyslnych."""
        assert get_signature_position({}, Path("/tmp/doc.pdf"), 11, 22) == (11.0, 22.0)


class TestSaveSignaturePosition:
    def test_save_to_empty_file(self, tmp_path: Path):
        """Zapis do nieistniejacego pliku."""
        config_file = tmp_path / "config.toml"
        pdf = Path("/tmp/doc.pdf")
        save_signature_position(config_file, pdf, 42.5, 67.8)

        content = config_file.read_text(encoding="utf-8")
        assert '[signatures."/tmp/doc.pdf"]' in content
        assert "x = 42.5" in content
        assert "y = 67.8" in content

    def test_append_to_existing(self, tmp_path: Path):
        """Dodanie do istniejacego pliku nie nadpisuje innych sekcji."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[credentials]\nusername = "jan"\npassword = "x"\n',
            encoding="utf-8",
        )
        save_signature_position(config_file, Path("/tmp/doc.pdf"), 50.0, 60.0)

        content = config_file.read_text(encoding="utf-8")
        assert "[credentials]" in content
        assert 'username = "jan"' in content
        assert '[signatures."/tmp/doc.pdf"]' in content

    def test_update_existing_entry(self, tmp_path: Path):
        """Aktualizacja istniejacego wpisu dla tej samej sciezki."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[signatures."/tmp/doc.pdf"]\nx = 10.0\ny = 20.0\n',
            encoding="utf-8",
        )
        save_signature_position(config_file, Path("/tmp/doc.pdf"), 55.5, 66.6)

        content = config_file.read_text(encoding="utf-8")
        assert "x = 55.5" in content
        assert "y = 66.6" in content
        assert "x = 10.0" not in content
        assert "y = 20.0" not in content

    def test_roundtrip(self, tmp_path: Path):
        """Zapis i odczyt dajacy te same wartosci."""
        config_file = tmp_path / "config.toml"
        pdf = Path("/tmp/doc.pdf")
        save_signature_position(config_file, pdf, 33.3, 77.7)

        loaded = load_config(config_file)
        assert find_signature_position(loaded, pdf) == pytest.approx((33.3, 77.7))
