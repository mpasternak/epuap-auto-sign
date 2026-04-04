"""Obsługa pliku konfiguracyjnego config.toml."""

from __future__ import annotations

import fnmatch
import logging
import re
import tomllib
from pathlib import Path

from .constants import DEFAULT_CONFIG_FILENAME

logger = logging.getLogger(__name__)


def resolve_config_path(config_path: Path | None = None) -> Path:
    """Zwraca rzeczywistą ścieżkę do pliku konfiguracyjnego."""
    if config_path is None:
        return Path(DEFAULT_CONFIG_FILENAME)
    return config_path


def load_config(config_path: Path | None = None) -> dict:
    """Wczytuje plik config.toml i zwraca słownik.

    Jeśli plik nie istnieje, zwraca pusty słownik.
    """
    path = resolve_config_path(config_path)
    if not path.is_file():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_credentials(config: dict) -> dict[str, str] | None:
    """Wyciąga dane logowania (username, password) z konfiguracji.

    Zwraca None jeśli nie są kompletne.
    """
    creds = config.get("credentials", {})
    if creds.get("username") and creds.get("password"):
        return {"username": creds["username"], "password": creds["password"]}
    return None


def find_signature_position(config: dict, pdf_path: Path) -> tuple[float, float] | None:
    """Szuka pozycji podpisu dla pliku w sekcji [signatures] konfiguracji.

    Wzorce są sprawdzane w kolejności; pierwszy pasujący wygrywa.
    Obsługuje wzorce glob (fnmatch), np. '/Users/foo/*.pdf'.

    Returns:
        Krotka (x_pct, y_pct) lub None jeśli brak dopasowania.
    """
    signatures = config.get("signatures", {})
    pdf_str = str(pdf_path)
    for pattern, pos in signatures.items():
        if fnmatch.fnmatch(pdf_str, pattern):
            x = float(pos.get("x", 50))
            y = float(pos.get("y", 66))
            logger.info(
                "Znaleziono pozycje podpisu dla '%s': x=%.1f%%, y=%.1f%%",
                pattern,
                x,
                y,
            )
            return (x, y)
    return None


def get_signature_position(
    config: dict, pdf_path: Path, default_x: float, default_y: float
) -> tuple[float, float]:
    """Zwraca pozycję podpisu dla pliku.

    Kolejność priorytetu:
    1. Dopasowanie w [signatures] (najbardziej specyficzne)
    2. Ustawienie globalne w [signature]
    3. Wartości domyślne przekazane jako argumenty
    """
    matched = find_signature_position(config, pdf_path)
    if matched:
        return matched

    sig_config = config.get("signature", {})
    x = float(sig_config.get("x", default_x))
    y = float(sig_config.get("y", default_y))
    return (x, y)


def save_signature_position(config_path: Path, pdf_path: Path, x_pct: float, y_pct: float) -> None:
    """Zapisuje pozycję podpisu dla pliku w config.toml.

    Dodaje lub aktualizuje sekcję [signatures."<ścieżka>"].
    Klucz to pełna ścieżka do pliku.
    """
    content = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""

    pdf_key = str(pdf_path)

    # Wzorzec: [signatures."<path>"] + x = ... + y = ...
    section_pattern = re.compile(
        r'\[signatures\."' + re.escape(pdf_key) + r'"\]\s*\n'
        r"x\s*=\s*[\d.]+\s*\n"
        r"y\s*=\s*[\d.]+\s*\n?",
    )
    new_section = f'[signatures."{pdf_key}"]\n' f"x = {x_pct:.1f}\n" f"y = {y_pct:.1f}\n"

    if section_pattern.search(content):
        content = section_pattern.sub(new_section, content)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n{new_section}"

    config_path.write_text(content, encoding="utf-8")
    logger.info(
        "Zapisano pozycje podpisu (x=%.1f%%, y=%.1f%%) dla '%s'",
        x_pct,
        y_pct,
        pdf_key,
    )
