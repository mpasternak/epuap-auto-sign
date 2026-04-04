"""Główny moduł: orkiestracja procesu podpisywania dokumentu PDF."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from playwright.sync_api import Download, sync_playwright

from .browser import wait_and_click
from .config import (
    get_signature_position,
    load_config,
    load_credentials,
    resolve_config_path,
)
from .constants import (
    DEFAULT_SIG_X_PCT,
    DEFAULT_SIG_Y_PCT,
    DEFAULT_SIGN_METHOD,
    SIGNER_URL,
)
from .login import fill_login_form, handle_sms_code
from .signature import adjust_signature_position

logger = logging.getLogger(__name__)


def _determine_output_path(pdf_path: Path, output_path: Path | None) -> Path:
    """Wyznacza ścieżkę pliku wyjściowego.

    Jeśli nie podano, używa nazwy oryginalnej z sufiksem _signed
    i zachowuje oryginalne rozszerzenie (PDF zostaje PDF).
    """
    if output_path is None:
        return pdf_path.with_name(f"{pdf_path.stem}_signed{pdf_path.suffix}").resolve()
    return Path(output_path).resolve()


def sign_pdf(
    pdf_path: Path,
    output_path: Path | None = None,
    timeout_ms: int = 300_000,
    sign_method: str = DEFAULT_SIGN_METHOD,
    config_path: Path | None = None,
    sig_x_pct: float = DEFAULT_SIG_X_PCT,
    sig_y_pct: float = DEFAULT_SIG_Y_PCT,
    headless: bool = False,
) -> Path:
    """Podpisuje plik PDF podpisem zaufanym przez portal podpis.gov.pl.

    Otwiera okno przeglądarki, uploaduje plik, wypełnia formularz logowania
    (jeśli są dane w config.toml), czeka na kody SMS, a na końcu pobiera
    podpisany dokument.

    Args:
        pdf_path: Ścieżka do pliku PDF do podpisania.
        output_path: Gdzie zapisać podpisany plik.
            Domyślnie: <nazwa>_signed<oryginalne_rozszerzenie>.
        timeout_ms: Maksymalny czas oczekiwania na pobranie (ms).
        sign_method: Metoda podpisu wyświetlana na stronie
            (np. "Profil zaufany", "Certyfikat kwalifikowany").
        config_path: Ścieżka do config.toml.
        sig_x_pct: Pozycja pozioma podpisu w procentach (0-100).
        sig_y_pct: Pozycja pionowa podpisu w procentach (0-100).
        headless: Czy uruchomić przeglądarkę w trybie headless
            (NIE ZALECANE - logowanie wymaga interakcji).

    Returns:
        Ścieżka do zapisanego, podpisanego pliku.

    Raises:
        FileNotFoundError: Jeśli plik PDF nie istnieje.
        RuntimeError: Jeśli nie udało się pobrać podpisanego pliku.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Plik nie istnieje: {pdf_path}")

    output_path = _determine_output_path(pdf_path, output_path)

    resolved_config_path = resolve_config_path(config_path)
    config = load_config(config_path)
    credentials = load_credentials(config)
    if credentials:
        logger.info("Znaleziono dane logowania w config.toml")
    else:
        logger.info("Brak config.toml - logowanie reczne w przegladarce.")

    sig_x_pct, sig_y_pct = get_signature_position(config, pdf_path, sig_x_pct, sig_y_pct)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Nasłuchiwanie na event download
        download_event = threading.Event()
        captured_download: list[Download] = []

        def on_download(download: Download) -> None:
            logger.info("Pobieranie pliku: %s", download.suggested_filename)
            captured_download.append(download)
            download_event.set()

        page.on("download", on_download)

        # Krok 1: Otwarcie strony
        logger.info("Otwieram strone podpis.gov.pl...")
        page.goto(SIGNER_URL)
        page.wait_for_load_state("networkidle")

        # Krok 2: Zamknięcie klauzuli RODO
        logger.info("Zamykam okno klauzuli...")
        close_button = page.locator('button:has-text("Zamknij")')
        try:
            close_button.wait_for(state="visible", timeout=10_000)
            close_button.click()
            logger.info("Okno klauzuli zamkniete.")
            page.wait_for_timeout(500)
        except Exception:
            logger.debug("Brak okna klauzuli lub juz zamkniete.")

        # Krok 3: Upload pliku
        logger.info("Laduje plik: %s", pdf_path.name)
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(str(pdf_path))
        logger.info("Plik zaladowany.")

        # Krok 4: "Dalej"
        wait_and_click(page, ['button:has-text("Dalej")'], "Dalej")

        # Krok 4a: Podgląd + ustawienie pozycji podpisu
        adjust_signature_position(page, sig_x_pct, sig_y_pct, pdf_path, resolved_config_path)

        # Krok 5: "Podpisz"
        wait_and_click(
            page,
            [
                'button:has-text("Podpisz podpisem zaufanym")',
                'button:has-text("Podpisz")',
                'a:has-text("Podpisz")',
            ],
            "Podpisz",
        )

        # Krok 6: Wybór metody podpisu
        wait_and_click(
            page,
            [
                f'button:has-text("{sign_method}")',
                f'a:has-text("{sign_method}")',
                f'[role="button"]:has-text("{sign_method}")',
                f'label:has-text("{sign_method}")',
            ],
            sign_method,
        )

        # Krok 7: Logowanie
        if credentials:
            page.wait_for_timeout(3000)
            fill_login_form(page, credentials)

        # Krok 8: Kod SMS do logowania
        handle_sms_code(page, label="logowanie")

        # Krok 9: Kod SMS do podpisu
        handle_sms_code(page, label="podpis")

        # Krok 10: "Pobierz podpisane dokumenty"
        logger.info("Czekam na mozliwosc pobrania podpisanych dokumentow...")
        wait_and_click(
            page,
            [
                'button:has-text("Pobierz podpisane dokumenty")',
                'a:has-text("Pobierz podpisane dokumenty")',
                'button:has-text("Pobierz")',
                'a:has-text("Pobierz")',
            ],
            "Pobierz podpisane dokumenty",
        )

        # Krok 11: Oczekiwanie na pobranie
        logger.info(
            "Oczekiwanie na pobranie pliku (timeout: %d s)...",
            timeout_ms // 1000,
        )

        poll_interval_ms = 2000
        elapsed = 0
        while not download_event.is_set() and elapsed < timeout_ms:
            page.wait_for_timeout(poll_interval_ms)
            elapsed += poll_interval_ms
            if elapsed % 30_000 == 0:
                logger.info(
                    "Nadal czekam na pobranie... (%d/%d s)",
                    elapsed // 1000,
                    timeout_ms // 1000,
                )

        if not captured_download:
            raise RuntimeError("Timeout - nie pobrano podpisanego pliku.")

        download = captured_download[0]
        # Jeśli nie podano output_path, dopasuj rozszerzenie do pobranego pliku
        if output_path.suffix != Path(download.suggested_filename).suffix:
            suggested_suffix = Path(download.suggested_filename).suffix
            if suggested_suffix:
                output_path = output_path.with_suffix(suggested_suffix)
                logger.info(
                    "Dopasowano rozszerzenie pliku do oryginalu: %s",
                    output_path.suffix,
                )

        download.save_as(str(output_path))
        logger.info("Zapisano podpisany plik: %s", output_path)

        browser.close()

    return output_path
