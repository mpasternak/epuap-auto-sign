"""Obsługa pozycjonowania znaku graficznego podpisu w podglądzie dokumentu."""

from __future__ import annotations

import logging
from pathlib import Path

from .browser import wait_and_click
from .config import save_signature_position

logger = logging.getLogger(__name__)

PREVIEW_LINK_SELECTORS = [
    'button:has-text("pokaż podgląd")',
    'button:has-text("Pokaż podgląd")',
    'a:has-text("pokaż podgląd")',
    'a:has-text("Pokaż podgląd")',
    ':has-text("podgląd dokumentu")',
]

SAVE_BUTTON_SELECTORS = [
    'button:has-text("Zapisz")',
    'button:has-text("zapisz")',
    'a:has-text("Zapisz")',
]


def calculate_target_position(
    boundary_box: dict,
    sig_width: float,
    sig_height: float,
    x_pct: float,
    y_pct: float,
) -> tuple[float, float]:
    """Oblicza docelowe współrzędne środka podpisu na ekranie.

    Args:
        boundary_box: Bounding box kontenera dokumentu
            (słownik z kluczami: x, y, width, height).
        sig_width: Szerokość elementu podpisu w pikselach.
        sig_height: Wysokość elementu podpisu w pikselach.
        x_pct: Pozycja pozioma w procentach (0-100).
        y_pct: Pozycja pionowa w procentach (0-100).

    Returns:
        Krotka (target_x, target_y) - środek podpisu na ekranie.
    """
    usable_w = boundary_box["width"] - sig_width
    usable_h = boundary_box["height"] - sig_height

    target_x = boundary_box["x"] + usable_w * (x_pct / 100) + sig_width / 2
    target_y = boundary_box["y"] + usable_h * (y_pct / 100) + sig_height / 2

    return (target_x, target_y)


def calculate_current_percentage(sig_box: dict, boundary_box: dict) -> tuple[float, float] | None:
    """Oblicza aktualną pozycję podpisu w procentach (operacja odwrotna
    do calculate_target_position).

    Args:
        sig_box: Bounding box elementu podpisu.
        boundary_box: Bounding box kontenera dokumentu.

    Returns:
        Krotka (x_pct, y_pct) lub None jeśli brak wystarczającej przestrzeni.
    """
    usable_w = boundary_box["width"] - sig_box["width"]
    usable_h = boundary_box["height"] - sig_box["height"]

    if usable_w <= 0 or usable_h <= 0:
        return None

    x_pct = (sig_box["x"] - boundary_box["x"]) / usable_w * 100
    y_pct = (sig_box["y"] - boundary_box["y"]) / usable_h * 100

    # Clamp do 0-100
    x_pct = max(0.0, min(100.0, x_pct))
    y_pct = max(0.0, min(100.0, y_pct))

    return (x_pct, y_pct)


def read_current_signature_pct(page) -> tuple[float, float] | None:
    """Odczytuje aktualną pozycję podpisu na stronie jako procenty."""
    sig_element = page.locator("#signature")
    boundary = page.locator(".boundary")

    try:
        sig_box = sig_element.bounding_box()
        boundary_box = boundary.bounding_box()
    except Exception:
        return None

    if not sig_box or not boundary_box:
        return None

    return calculate_current_percentage(sig_box, boundary_box)


def drag_signature(page, src_x: float, src_y: float, target_x: float, target_y: float) -> None:
    """Wykonuje drag-and-drop elementu podpisu.

    Angular CDK Drag wymaga inkrementalnych ruchów myszką - nie zadziała
    jedno wywołanie mouse.move(). Dlatego ruch jest podzielony na kroki.
    """
    page.mouse.move(src_x, src_y)
    page.wait_for_timeout(200)
    page.mouse.down()
    page.wait_for_timeout(200)

    steps = 30
    for i in range(1, steps + 1):
        intermediate_x = src_x + (target_x - src_x) * i / steps
        intermediate_y = src_y + (target_y - src_y) * i / steps
        page.mouse.move(intermediate_x, intermediate_y)
        page.wait_for_timeout(20)

    page.wait_for_timeout(200)
    page.mouse.up()


def adjust_signature_position(
    page,
    sig_x_pct: float,
    sig_y_pct: float,
    pdf_path: Path,
    config_path: Path,
    prompt_func=input,
) -> None:
    """Otwiera podgląd dokumentu i przesuwa znak podpisu na zadaną pozycję.

    Element podpisu to Angular CDK Drag (id="signature" z cdkDrag), osadzony
    w kontenerze .boundary. Pozycjonowanie odbywa się przez transform: translate3d().

    Po potwierdzeniu przez użytkownika, końcowa pozycja jest zapisywana
    do config.toml w sekcji [signatures."<pdf_path>"].

    Args:
        page: Obiekt strony Playwright.
        sig_x_pct: Pozycja pozioma w procentach (0-100).
        sig_y_pct: Pozycja pionowa w procentach (0-100).
        pdf_path: Pełna ścieżka do podpisywanego pliku (klucz w config).
        config_path: Ścieżka do config.toml.
        prompt_func: Funkcja do potwierdzenia przez użytkownika.
    """
    if not wait_and_click(page, PREVIEW_LINK_SELECTORS, "pokaż podgląd dokumentu"):
        logger.info("Nie znaleziono linku podgladu. Pomijam ustawianie pozycji.")
        return

    logger.info("Czekam na zaladowanie podgladu dokumentu...")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    sig_element = page.locator("#signature")
    try:
        sig_element.wait_for(state="visible", timeout=15_000)
    except Exception:
        logger.warning("Nie znaleziono elementu #signature!")
        prompt_func("\n*** Nie znaleziono podpisu. Nacisnij ENTER aby kontynuowac: ")
        return

    boundary = page.locator(".boundary")
    try:
        boundary.wait_for(state="visible", timeout=10_000)
    except Exception:
        logger.warning("Nie znaleziono kontenera .boundary!")
        prompt_func("\n*** Nie znaleziono kontenera. Nacisnij ENTER aby kontynuowac: ")
        return

    sig_box = sig_element.bounding_box()
    boundary_box = boundary.bounding_box()

    if not sig_box or not boundary_box:
        logger.warning("Nie udalo sie odczytac pozycji elementow.")
        prompt_func("\n*** Nie udalo sie odczytac pozycji. Nacisnij ENTER: ")
        return

    logger.debug("  #signature bounding_box: %s", sig_box)
    logger.debug("  .boundary bounding_box: %s", boundary_box)

    target_x, target_y = calculate_target_position(
        boundary_box, sig_box["width"], sig_box["height"], sig_x_pct, sig_y_pct
    )

    src_x = sig_box["x"] + sig_box["width"] / 2
    src_y = sig_box["y"] + sig_box["height"] / 2

    logger.info(
        "Przeciagam podpis: (%.0f, %.0f) -> (%.0f, %.0f) [cel: %.0f%% x %.0f%%]",
        src_x,
        src_y,
        target_x,
        target_y,
        sig_x_pct,
        sig_y_pct,
    )

    drag_signature(page, src_x, src_y, target_x, target_y)

    page.wait_for_timeout(500)
    new_sig_box = sig_element.bounding_box()
    if new_sig_box and sig_box:
        dx = new_sig_box["x"] - sig_box["x"]
        dy = new_sig_box["y"] - sig_box["y"]
        logger.info("Podpis przesuniety o (%.0f, %.0f) pikseli.", dx, dy)
        if abs(dx) < 5 and abs(dy) < 5:
            logger.warning("Podpis NIE zmienil pozycji! Sprawdz recznie.")

    # Pauza na weryfikację/korektę
    print("\a", end="", flush=True)
    prompt_func(
        "\n*** Sprawdz/popraw pozycje podpisu w przegladarce. "
        "Nacisnij ENTER aby zapisac i kontynuowac: "
    )

    # Odczyt i zapis końcowej pozycji
    final_pos = read_current_signature_pct(page)
    if final_pos:
        logger.info(
            "Koncowa pozycja podpisu: x=%.1f%%, y=%.1f%%",
            final_pos[0],
            final_pos[1],
        )
        save_signature_position(config_path, pdf_path, final_pos[0], final_pos[1])
    else:
        logger.warning("Nie udalo sie odczytac koncowej pozycji podpisu.")

    wait_and_click(page, SAVE_BUTTON_SELECTORS, "Zapisz")
    page.wait_for_timeout(2000)
