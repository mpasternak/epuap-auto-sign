"""Testy modulu signature."""

from __future__ import annotations

import pytest

from epuap_auto_sign.signature import (
    calculate_current_percentage,
    calculate_target_position,
)


class TestCalculateTargetPosition:
    def test_center(self):
        """50%, 50% daje srodek kontenera."""
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        target = calculate_target_position(boundary, 100, 100, 50, 50)
        # Srodek podpisu powinien byc na srodku kontenera
        assert target == (500.0, 500.0)

    def test_top_left_corner(self):
        """0%, 0% daje lewy gorny rog (srodek podpisu = pol rozmiaru)."""
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        target = calculate_target_position(boundary, 100, 100, 0, 0)
        assert target == (50.0, 50.0)

    def test_bottom_right_corner(self):
        """100%, 100% daje prawy dolny rog."""
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        target = calculate_target_position(boundary, 100, 100, 100, 100)
        # signature: x w [0, 900], srodek w (900+50, 900+50) = (950, 950)
        assert target == (950.0, 950.0)

    def test_offset_boundary(self):
        """Kontener z przesunieciem."""
        boundary = {"x": 100, "y": 200, "width": 800, "height": 600}
        target = calculate_target_position(boundary, 200, 100, 50, 50)
        # usable_w = 600, usable_h = 500
        # target_x = 100 + 600*0.5 + 100 = 500
        # target_y = 200 + 500*0.5 + 50 = 500
        assert target == (500.0, 500.0)

    def test_two_thirds_position(self):
        """66% daje 2/3 kontenera."""
        boundary = {"x": 0, "y": 0, "width": 900, "height": 900}
        target = calculate_target_position(boundary, 100, 100, 66, 66)
        # usable = 800, target = 800*0.66 + 50 = 578
        assert target[0] == pytest.approx(578.0)
        assert target[1] == pytest.approx(578.0)


class TestCalculateCurrentPercentage:
    def test_center(self):
        """Podpis na srodku = 50%, 50%."""
        sig = {"x": 450, "y": 450, "width": 100, "height": 100}
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        result = calculate_current_percentage(sig, boundary)
        assert result == (50.0, 50.0)

    def test_top_left(self):
        """Podpis w lewym gornym rogu = 0%, 0%."""
        sig = {"x": 0, "y": 0, "width": 100, "height": 100}
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        result = calculate_current_percentage(sig, boundary)
        assert result == (0.0, 0.0)

    def test_bottom_right(self):
        """Podpis w prawym dolnym rogu = 100%, 100%."""
        sig = {"x": 900, "y": 900, "width": 100, "height": 100}
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        result = calculate_current_percentage(sig, boundary)
        assert result == (100.0, 100.0)

    def test_no_usable_space(self):
        """Podpis wiekszy niz kontener -> None."""
        sig = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        boundary = {"x": 0, "y": 0, "width": 500, "height": 500}
        assert calculate_current_percentage(sig, boundary) is None

    def test_exact_fit(self):
        """Podpis idealnie wypelnia kontener -> None (usable = 0)."""
        sig = {"x": 0, "y": 0, "width": 500, "height": 500}
        boundary = {"x": 0, "y": 0, "width": 500, "height": 500}
        assert calculate_current_percentage(sig, boundary) is None

    def test_clamping(self):
        """Wartosci poza zakresem sa przyciete do 0-100."""
        sig = {"x": -50, "y": 2000, "width": 100, "height": 100}
        boundary = {"x": 0, "y": 0, "width": 1000, "height": 1000}
        result = calculate_current_percentage(sig, boundary)
        assert result == (0.0, 100.0)


class TestRoundtrip:
    """Sprawdzenie ze calculate_target_position i calculate_current_percentage
    sa wzajemnie odwrotne."""

    @pytest.mark.parametrize("x_pct,y_pct", [(0, 0), (25, 75), (50, 50), (66, 66), (100, 100)])
    def test_roundtrip(self, x_pct: float, y_pct: float):
        boundary = {"x": 10, "y": 20, "width": 800, "height": 600}
        sig_w, sig_h = 150, 80

        # Oblicz pozycje docelowa (srodek podpisu)
        target_x, target_y = calculate_target_position(boundary, sig_w, sig_h, x_pct, y_pct)

        # Skonstruuj bounding box z srodkiem w (target_x, target_y)
        sig_box = {
            "x": target_x - sig_w / 2,
            "y": target_y - sig_h / 2,
            "width": sig_w,
            "height": sig_h,
        }

        # Odczytaj procenty wstecz
        result = calculate_current_percentage(sig_box, boundary)
        assert result is not None
        assert result[0] == pytest.approx(x_pct)
        assert result[1] == pytest.approx(y_pct)
