"""Test integracyjny przeciagania podpisu z przewijaniem strony.

Modeluje kluczowe ograniczenie: page.mouse operuje na wspolrzednych
viewportu (widocznego okna). Element pod foldem ma bounding_box z y
wiekszym niz wysokosc okna - drag na takich wspolrzednych nie dziala.
Przed odczytem wspolrzednych strona musi zostac przewinieta tak,
by podglad dokumentu byl widoczny.
"""

from __future__ import annotations

import re
from pathlib import Path

from epuap_auto_sign.signature import adjust_signature_position

VIEWPORT_HEIGHT = 700


class FakeDomElement:
    """Element w dokumencie - pozycja w ukladzie dokumentu (nie viewportu)."""

    def __init__(self, doc_x: float, doc_y: float, width: float, height: float):
        self.doc_x = doc_x
        self.doc_y = doc_y
        self.width = width
        self.height = height


class FakeLocator:
    def __init__(self, page: FakeDragPage, selector: str):
        self.page = page
        self.selector = selector

    @property
    def first(self) -> FakeLocator:
        return self

    def _element(self) -> FakeDomElement | None:
        return self.page.elements.get(self.selector)

    def is_visible(self, timeout: int | None = None) -> bool:
        return self._element() is not None

    def wait_for(self, state: str = "visible", timeout: int | None = None) -> None:
        if self._element() is None:
            raise TimeoutError(f"Brak elementu {self.selector}")

    def click(self, **kwargs) -> None:
        if self._element() is None:
            raise TimeoutError(f"Brak elementu {self.selector}")
        self.page.clicked.append(self.selector)

    def bounding_box(self) -> dict | None:
        element = self._element()
        if element is None:
            return None
        return {
            "x": element.doc_x,
            "y": element.doc_y - self.page.scroll_y,
            "width": element.width,
            "height": element.height,
        }

    def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
        element = self._element()
        if element is None:
            raise TimeoutError(f"Brak elementu {self.selector}")
        top = element.doc_y - self.page.scroll_y
        bottom = top + element.height
        if top >= 0 and bottom <= VIEWPORT_HEIGHT:
            return  # juz w pelni widoczny
        # przegladarka dosuwa gorna krawedz elementu do gornej krawedzi okna
        self.page.scroll_y = max(0.0, element.doc_y - 20)


class FakeMouse:
    """Rejestruje ruchy myszy; po mouse.up() przenosi podpis w miejsce
    ostatniego ruchu (jak Angular CDK Drag)."""

    def __init__(self, page: FakeDragPage):
        self.page = page
        self.positions: list[tuple[float, float]] = []
        self.dragging = False

    def move(self, x: float, y: float, **kwargs) -> None:
        self.positions.append((x, y))

    def down(self) -> None:
        self.dragging = True

    def up(self) -> None:
        self.dragging = False
        sig = self.page.elements["#signature"]
        last_x, last_y = self.positions[-1]
        sig.doc_x = last_x - sig.width / 2
        sig.doc_y = (last_y + self.page.scroll_y) - sig.height / 2


class FakeDragPage:
    def __init__(self, elements: dict[str, FakeDomElement]):
        self.elements = elements
        self.scroll_y = 0.0
        self.clicked: list[str] = []
        self.mouse = FakeMouse(self)

    # W trybie no_viewport Playwright zwraca None - rozmiar trzeba
    # odczytac przez window.innerHeight.
    viewport_size = None

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def wait_for_timeout(self, ms: int) -> None:
        pass  # w tescie czas nie plynie

    def wait_for_load_state(self, state: str) -> None:
        pass  # strona w tescie jest zawsze zaladowana

    def evaluate(self, script: str, arg=None):
        if "innerHeight" in script:
            return VIEWPORT_HEIGHT
        if "scrollBy" in script:
            self.scroll_y += arg
            return None
        raise NotImplementedError(f"Nieobslugiwany skrypt: {script}")


def make_page_with_preview_below_fold() -> FakeDragPage:
    """Podglad dokumentu w calosci pod foldem (okno 700 px, dokument od 900 px)."""
    return FakeDragPage(
        {
            'button:has-text("pokaż podgląd")': FakeDomElement(10, 10, 100, 30),
            'button:has-text("Zapisz")': FakeDomElement(10, 60, 100, 30),
            ".boundary": FakeDomElement(100, 900, 800, 600),
            "#signature": FakeDomElement(150, 950, 100, 50),
        }
    )


def test_drag_odbywa_sie_w_widocznym_obszarze_okna(tmp_path: Path):
    """Podglad jest pod foldem - strona musi zostac przewinieta, a wszystkie
    ruchy myszy musza miec wspolrzedne w obrebie okna (0..700), inaczej
    drag nie dziala. Koncowa pozycja ma odpowiadac zadanym procentom."""
    page = make_page_with_preview_below_fold()
    config_path = tmp_path / "config.toml"

    adjust_signature_position(
        page,
        sig_x_pct=50.0,
        sig_y_pct=66.0,
        pdf_path=tmp_path / "dokument.pdf",
        config_path=config_path,
        prompt_func=lambda _: "",
    )

    assert page.mouse.positions, "Drag w ogole sie nie odbyl"
    for _x, y in page.mouse.positions:
        assert 0 <= y <= VIEWPORT_HEIGHT, (
            f"Ruch myszy poza widocznym obszarem okna: y={y} (okno {VIEWPORT_HEIGHT} px)"
        )

    # Koncowa pozycja podpisu zapisana w config.toml odpowiada zadaniu
    content = config_path.read_text(encoding="utf-8")
    x_match = re.search(r"x\s*=\s*([\d.]+)", content)
    y_match = re.search(r"y\s*=\s*([\d.]+)", content)
    assert x_match and y_match, f"Brak zapisanej pozycji w config: {content!r}"
    assert float(x_match.group(1)) == 50.0
    assert float(y_match.group(1)) == 66.0

    assert 'button:has-text("Zapisz")' in page.clicked
