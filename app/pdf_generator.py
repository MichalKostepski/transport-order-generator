from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import fitz


# Neutral safety text for the public portfolio version.
# Company-specific operating instructions are intentionally not included.
SPECIAL_NOTES_TITLE = "Handling and load securing instructions"
SPECIAL_NOTES_XL = (
    "Secure the cargo according to applicable transport regulations and the carrier's "
    "approved procedures. Verify loading conditions and the suitability of securing equipment."
)
SPECIAL_NOTES_L = (
    "This source release is a demonstration. Actual operating instructions must be provided "
    "and approved by the relevant company before any real transport takes place."
)


class PdfGenerator:
    def __init__(self, config_path: Path):
        self.base_dir = config_path.resolve().parent
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        pdf_settings = config["pdf"]
        self.demo_mode = bool(pdf_settings.get("demo_mode", False))
        self.template_path = self._resolve_path(pdf_settings["template_path"])
        self.output_dir = self._resolve_path(pdf_settings["output_directory"], desktop_token=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.regular_font = self._find_font(bold=False)
        self.bold_font = self._find_font(bold=True)

    def _resolve_path(self, value: Any, desktop_token: bool = False) -> Path:
        raw = str(value or "").strip()
        if desktop_token and raw.upper().startswith("%DESKTOP%"):
            desktop = os.environ.get("TRANSPORT_DESKTOP_DIR", "").strip()
            if desktop:
                base = Path(desktop)
            else:
                base = Path.home() / "Desktop"
            suffix = raw[len("%DESKTOP%") :].lstrip("\\/")
            return (base / suffix).resolve()
        expanded = os.path.expandvars(os.path.expanduser(raw))
        path = Path(expanded)
        return path.resolve() if path.is_absolute() else (self.base_dir / path).resolve()

    @staticmethod
    def _find_font(bold: bool) -> Optional[str]:
        candidates = []
        if os.name == "nt":
            windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
            candidates.extend([
                windows_fonts / ("arialbd.ttf" if bold else "arial.ttf"),
                windows_fonts / ("calibrib.ttf" if bold else "calibri.ttf"),
            ])
        candidates.extend([
            Path(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
            Path(
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
            ),
        ])
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _safe_filename(order_number: str) -> str:
        value = re.sub(r"[^0-9A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż._-]+", "_", order_number)
        return value.strip("_.") or "zamowienie"

    def _font_names(self, page: fitz.Page) -> tuple[str, str]:
        regular_name = "app_regular"
        bold_name = "app_bold"
        if self.regular_font:
            page.insert_font(fontname=regular_name, fontfile=self.regular_font)
        else:
            regular_name = "helv"
        if self.bold_font:
            page.insert_font(fontname=bold_name, fontfile=self.bold_font)
        else:
            bold_name = "hebo"
        return regular_name, bold_name

    @staticmethod
    def _draw_white_box(page: fitz.Page, rect: fitz.Rect) -> None:
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)

    @staticmethod
    def _insert_box(
        page: fitz.Page,
        rect: fitz.Rect,
        text: str,
        fontname: str,
        fontsize: float,
        align: int = fitz.TEXT_ALIGN_LEFT,
        lineheight: float = 1.15,
    ) -> float:
        return page.insert_textbox(
            rect,
            text or "",
            fontname=fontname,
            fontsize=fontsize,
            color=(0, 0, 0),
            align=align,
            lineheight=lineheight,
            overlay=True,
        )

    @staticmethod
    def _insert_fitted_line(
        page: fitz.Page,
        x: float,
        baseline_y: float,
        max_x: float,
        text: str,
        fontname: str,
        fontsize: float,
        min_fontsize: float = 7.5,
    ) -> None:
        """Insert one value on the exact baseline of the printed rubric."""
        value = " ".join(str(text or "").replace("\n", " ").split())
        if not value:
            return
        size = float(fontsize)
        # Helvetica is close enough for width estimation even when Arial is embedded.
        while size > min_fontsize and fitz.get_text_length(value, fontname="helv", fontsize=size) > max_x - x:
            size -= 0.25
        page.insert_text(
            fitz.Point(x, baseline_y),
            value,
            fontname=fontname,
            fontsize=max(min_fontsize, size),
            color=(0, 0, 0),
            overlay=True,
        )

    @staticmethod
    def _split_place(name: Any, address: Any) -> tuple[str, str]:
        raw_name = str(name or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        raw_address = str(address or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        lines = [line.strip() for line in raw_name.split("\n") if line.strip()]
        if len(lines) > 1:
            raw_name = lines[0]
            extra = "\n".join(lines[1:])
            if not raw_address:
                raw_address = extra
            elif extra and extra.casefold() not in raw_address.casefold():
                raw_address = f"{extra}\n{raw_address}"
        if not raw_address and "  -  " in raw_name:
            left, right = raw_name.split("  -  ", 1)
            if left.strip() and right.strip():
                raw_name, raw_address = left.strip(), right.strip()
        return raw_name.strip(), raw_address.strip()

    def _insert_place_block(
        self,
        page: fitz.Page,
        name: Any,
        address: Any,
        name_baseline: float,
        address_rect: fitz.Rect,
        fontname: str,
    ) -> None:
        clean_name, clean_address = self._split_place(name, address)
        self._insert_fitted_line(page, 43, name_baseline, 550, clean_name, fontname, 10.2, min_fontsize=8.5)
        if clean_address:
            result = self._insert_box(
                page,
                address_rect,
                clean_address,
                fontname,
                9.4,
                lineheight=1.22,
            )
            if result < 0:
                self._insert_box(page, address_rect, clean_address, fontname, 8.2, lineheight=1.15)

    @staticmethod
    def _date_pl(value: str) -> str:
        """Format every ISO date in a single date or date range."""
        text = str(value or "").strip()
        if not text:
            return ""
        return re.sub(
            r"\b(\d{4})-(\d{2})-(\d{2})\b",
            lambda match: f"{match.group(3)}.{match.group(2)}.{match.group(1)}",
            text,
        )

    @staticmethod
    def _tons_text(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value or "")
        if number.is_integer():
            return str(int(number))
        return (f"{number:.3f}").rstrip("0").rstrip(".").replace(".", ",")

    @staticmethod
    def _remove_old_special_notes(page: fitz.Page) -> None:
        # Remove the compact block from the source template before placing the roomier version.
        page.add_redact_annot(fitz.Rect(22, 734, 574, 832), fill=(1, 1, 1))
        page.apply_redactions()

    def _draw_special_notes(self, page: fitz.Page, regular: str, bold: str) -> None:
        title_result = self._insert_box(
            page,
            fitz.Rect(25, 733, 570, 747),
            SPECIAL_NOTES_TITLE,
            bold,
            7.25,
            lineheight=1.15,
        )
        first_result = self._insert_box(
            page,
            fitz.Rect(25, 747, 570, 778),
            SPECIAL_NOTES_XL,
            regular,
            6.25,
            lineheight=1.15,
        )
        second_result = self._insert_box(
            page,
            fitz.Rect(25, 779, 570, 829),
            SPECIAL_NOTES_L,
            regular,
            6.25,
            lineheight=1.15,
        )
        if min(title_result, first_result, second_result) < 0:
            raise RuntimeError("Blok uwag specjalnych nie mieści się na stronie PDF.")

    def expected_path(self, order: Dict[str, Any]) -> Path:
        year = int(order["order_year"])
        month = int(order["order_month"])
        return (
            self.output_dir
            / str(year)
            / f"{month:02d}"
            / f"{self._safe_filename(str(order['order_number']))}.pdf"
        )

    def generate(self, order: Dict[str, Any], destination: Optional[Path] = None) -> Path:
        if not self.template_path.exists():
            raise FileNotFoundError(f"Brak szablonu PDF: {self.template_path}")

        expected = self.expected_path(order)
        expected.parent.mkdir(parents=True, exist_ok=True)
        if destination is None:
            destination = expected
        else:
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)

        document = fitz.open(self.template_path)
        page = document[0]
        self._remove_old_special_notes(page)
        regular, bold = self._font_names(page)

        # Date and order number: hide the old placeholder, keep the original line.
        self._draw_white_box(page, fitz.Rect(486, 105, 566, 120))
        page.draw_line(
            fitz.Point(486, 118),
            fitz.Point(566, 118),
            color=(0, 0, 0),
            width=0.8,
            overlay=True,
        )
        self._insert_fitted_line(
            page,
            493,
            116.1,
            565,
            self._date_pl(str(order.get("order_date", ""))),
            bold,
            8.5,
            min_fontsize=8.0,
        )

        self._draw_white_box(page, fitz.Rect(407, 124, 505, 145))
        page.draw_line(
            fitz.Point(91, 145),
            fitz.Point(495, 145),
            color=(0, 0, 0),
            width=0.8,
            overlay=True,
        )
        self._insert_box(
            page,
            fitz.Rect(407, 125.5, 505, 144),
            str(order.get("order_number", "")),
            bold,
            11.5,
            align=fitz.TEXT_ALIGN_CENTER,
        )

        carrier_block = str(order.get("carrier_name", "")).strip()
        self._insert_fitted_line(page, 61, 169.0, 560, carrier_block, bold, 10.2, min_fontsize=8.5)

        load_date = self._date_pl(str(order.get("load_date", "")))
        unload_date = self._date_pl(str(order.get("unload_date", "")))
        self._insert_fitted_line(page, 201, 190.9, 555, load_date, bold, 10.5)
        self._insert_fitted_line(page, 212, 268.6, 555, unload_date, bold, 10.5)

        self._insert_place_block(
            page,
            order.get("load_place_name", ""),
            order.get("load_address", ""),
            211.0,
            fitz.Rect(43, 216.5, 550, 249.5),
            bold,
        )
        self._insert_place_block(
            page,
            order.get("unload_place_name", ""),
            order.get("unload_address", ""),
            289.0,
            fitz.Rect(43, 294.5, 550, 322.0),
            bold,
        )

        cargo = str(order.get("cargo_type", "")).strip()
        tons = self._tons_text(order.get("cargo_tons", 0))
        cargo_value = cargo
        if tons and tons != "0":
            cargo_value = f"{cargo} ({tons} ton)" if cargo else f"{tons} ton"

        # Exact y coordinates come from the original label baselines in the template.
        # This keeps values such as "Płatność: 1 250 zł" on one visual line.
        value_lines = [
            (144, 338.8, 560, str(order.get("service_value", "")), bold, 10.8),
            (105, 353.8, 560, str(order.get("payment", "")), bold, 10.8),
            (205, 368.8, 560, cargo_value, bold, 10.8),
            (130, 404.0, 560, str(order.get("driver_full_name", "")), bold, 10.5),
            (145, 428.0, 560, str(order.get("driver_id_card", "")), bold, 10.5),
            (102, 452.0, 560, str(order.get("driver_pesel", "")), bold, 10.5),
            (165, 476.0, 560, str(order.get("truck_registration", "")), bold, 10.5),
            (170, 500.0, 560, str(order.get("trailer_registration", "")), bold, 10.5),
            (122, 524.0, 560, str(order.get("driver_phone", "")), bold, 10.5),
        ]
        for x, baseline_y, max_x, text, font, size in value_lines:
            self._insert_fitted_line(page, x, baseline_y, max_x, text, font, size)

        if self.demo_mode:
            # Never include company-specific safety/handling notes in sample documents.
            page.draw_line((42, 735), (553, 735), color=(0.89, 0.92, 0.94), width=1)
            page.insert_text(
                (42, 750), "TRANSPORTDESK DEMO  /  FICTIONAL DATA ONLY",
                fontname="hebo", fontsize=8, color=(0.10, 0.37, 0.29),
            )
        else:
            self._draw_special_notes(page, regular, bold)

        document.set_metadata(
            {**document.metadata, "title": f"Zamówienie transportowe {order.get('order_number', '')}"}
        )
        document.save(destination, garbage=4, deflate=True)
        document.close()
        return destination.resolve()
