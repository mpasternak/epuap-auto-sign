"""Punkt wejscia CLI dla epuap-auto-sign."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .constants import (
    DEFAULT_SIG_X_PCT,
    DEFAULT_SIG_Y_PCT,
    DEFAULT_SIGN_METHOD,
)
from .signer import sign_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epuap-sign",
        description="Podpisz plik PDF podpisem zaufanym (Profil Zaufany).",
    )
    parser.add_argument(
        "pdf",
        type=Path,
        help="Sciezka do pliku PDF do podpisania",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Sciezka pliku wyjsciowego (domyslnie: <nazwa>_signed.pdf)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=300,
        help="Czas oczekiwania na pobranie w sekundach (domyslnie: 300)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Sciezka do config.toml (domyslnie: ./config.toml)",
    )
    parser.add_argument(
        "-m",
        "--method",
        type=str,
        default=DEFAULT_SIGN_METHOD,
        help=(
            f"Metoda podpisu (domyslnie: '{DEFAULT_SIGN_METHOD}'). "
            "Inne opcje zgodnie z tym co oferuje portal."
        ),
    )
    parser.add_argument(
        "-x",
        "--sig-x",
        type=float,
        default=DEFAULT_SIG_X_PCT,
        help=f"Pozycja pozioma podpisu w procentach (domyslnie: {DEFAULT_SIG_X_PCT})",
    )
    parser.add_argument(
        "-y",
        "--sig-y",
        type=float,
        default=DEFAULT_SIG_Y_PCT,
        help=f"Pozycja pionowa podpisu w procentach (domyslnie: {DEFAULT_SIG_Y_PCT})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Wlacz szczegolowe logowanie (DEBUG)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        result = sign_pdf(
            pdf_path=args.pdf,
            output_path=args.output,
            timeout_ms=args.timeout * 1000,
            sign_method=args.method,
            config_path=args.config,
            sig_x_pct=args.sig_x,
            sig_y_pct=args.sig_y,
        )
        print(f"Podpisany plik zapisano: {result}")
        return 0
    except FileNotFoundError as e:
        print(f"Blad: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Blad podpisywania: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPrzerwano.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
