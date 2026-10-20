from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import fitz
from PySide6.QtCore import QDate, QEvent, QModelIndex, QRectF, QStringListModel, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QPainter, QPalette, QPixmap, QTextCursor
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from database import Database
from driver_parser import parse_driver_text
from pdf_generator import PdfGenerator


SCRIPT_DIR = Path(__file__).resolve().parent
_ENV_ROOT = os.environ.get("TRANSPORT_APP_ROOT", "").strip()
if _ENV_ROOT:
    APP_ROOT = Path(_ENV_ROOT).resolve()
elif getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = APP_ROOT / "config.json"
ICON_PATH = APP_ROOT / "assets" / "app_icon.ico"


APP_STYLE = r"""
QWidget {
    color: #17212b;
    font-size: 10pt;
}
QMainWindow, QTabWidget::pane { background: #e7ebef; }
QTabBar::tab {
    background: #d7dde2;
    color: #17212b;
    padding: 8px 18px;
    border: 1px solid #bcc5cd;
    border-bottom: none;
}
QTabBar::tab:selected { background: #ffffff; font-weight: 700; }
QScrollArea { border: none; background: #d8dde1; }
QScrollArea > QWidget > QWidget { background: #d8dde1; }
QLabel { color: #17212b; background: transparent; }
QFrame#toolbar, QFrame#notesPanel {
    background: #f7f8f9;
    border-bottom: 1px solid #c5ccd2;
}
QFrame#notesPanel {
    border: 1px solid #c5ccd2;
    border-radius: 4px;
    margin: 7px 12px 0 12px;
}
QPushButton, QToolButton {
    min-height: 30px;
    color: #17212b;
    border-radius: 4px;
    border: 1px solid #9da7af;
    background: #ffffff;
    padding: 4px 10px;
}
QPushButton:hover, QToolButton:hover { background: #edf5ef; border-color: #218739; }
QPushButton#primary { background: #218739; color: #ffffff; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #176c2b; }
QPushButton#historyPdf {
    min-height: 26px;
    padding: 2px 9px;
    color: #ffffff;
    background: #287a3c;
    border: none;
    font-weight: 700;
}
QPushButton#historyPdf:hover { background: #1b622e; }
QPushButton#historyDelete {
    min-height: 26px;
    padding: 2px 9px;
    color: #ffffff;
    background: #b42318;
    border: none;
    font-weight: 700;
}
QPushButton#historyDelete:hover { background: #8f1c13; }
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {
    color: #111111;
    selection-color: #ffffff;
    selection-background-color: #176c2b;
    border: 1px solid #9ca6ae;
    border-radius: 3px;
    background: #ffffff;
}
QComboBox QAbstractItemView {
    color: #111111;
    background: #ffffff;
    selection-color: #ffffff;
    selection-background-color: #218739;
    border: 1px solid #7f8b93;
}
QComboBox[overlayField="true"], QLineEdit[overlayField="true"], QPlainTextEdit[overlayField="true"], QDateEdit[overlayField="true"], QSpinBox[overlayField="true"] {
    color: #111111;
    font-weight: 700;
    background: rgba(255, 252, 218, 246);
    border: 1px solid #b59524;
    border-radius: 2px;
    padding: 0px 5px;
}
QComboBox[overlayField="true"]::drop-down {
    width: 0px;
    border: none;
}
QComboBox[overlayField="true"]::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QComboBox[overlayField="true"][recordState="known"], QLineEdit[overlayField="true"][recordState="known"], QPlainTextEdit[overlayField="true"][recordState="known"] {
    background: rgba(229, 249, 232, 246);
    border: 1px solid #3c8b4c;
}
QComboBox[overlayField="true"][recordState="new"], QLineEdit[overlayField="true"][recordState="new"], QPlainTextEdit[overlayField="true"][recordState="new"] {
    background: rgba(255, 249, 214, 246);
    border: 1px solid #b59524;
}
QComboBox[overlayField="true"][recordState="empty"], QLineEdit[overlayField="true"][recordState="empty"], QPlainTextEdit[overlayField="true"][recordState="empty"] {
    background: rgba(255, 255, 255, 236);
    border: 1px dashed #9ca6ae;
}
QComboBox[overlayField="true"]:focus, QLineEdit[overlayField="true"]:focus, QPlainTextEdit[overlayField="true"]:focus, QDateEdit[overlayField="true"]:focus,
QSpinBox[overlayField="true"]:focus {
    border: 2px solid #176c2b;
    background: rgba(255, 255, 238, 252);
}
QLabel#numberSeparator {
    background: rgba(255,255,255,240);
    color: #111111;
    font-weight: 700;
}
QTableWidget {
    color: #111111;
    background: #ffffff;
    alternate-background-color: #f5f7f8;
    gridline-color: #dfe4e8;
}
QHeaderView::section {
    color: #111111;
    background: #e9edf0;
    padding: 5px;
    border: 1px solid #ccd3d8;
}
QStatusBar { color: #17212b; background: #f3f5f7; }
"""


class SmartCombo(QComboBox):
    """Editable field with database suggestions and exact-record indication."""

    recordSelected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None, placeholder: str = ""):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(12)
        self.setProperty("overlayField", True)
        self._known: set[str] = set()
        self._last_auto_emitted = ""

        if self.lineEdit():
            self.lineEdit().setPlaceholderText(placeholder)
            self.lineEdit().textEdited.connect(self._typing)
            self.lineEdit().editingFinished.connect(self._editing_finished)

        completer = QCompleter(self.model(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setMaxVisibleItems(12)
        completer.activated.connect(self._completion_selected)
        self.setCompleter(completer)
        self.currentTextChanged.connect(self._update_record_state)
        self._update_record_state("")

    @staticmethod
    def _normal(value: str) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    def set_values(self, values: Iterable[Any], keep_text: bool = True) -> None:
        old_text = self.currentText() if keep_text else ""
        clean: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            key = self._normal(text)
            if text and key not in seen:
                clean.append(text)
                seen.add(key)
        self.blockSignals(True)
        self.clear()
        self.addItems(clean)
        self.setCurrentText(old_text)
        self.blockSignals(False)
        self._known = seen
        self.completer().setModel(self.model())
        self._update_record_state(old_text)

    def text(self) -> str:
        return self.currentText().strip()

    def set_text(self, value: Any) -> None:
        self.setCurrentText(str(value or ""))
        self._update_record_state(self.currentText())

    def is_known_record(self) -> bool:
        return self._normal(self.currentText()) in self._known

    def _typing(self, text: str) -> None:
        self._update_record_state(text)
        normalized = self._normal(text)
        if normalized in self._known and normalized != self._last_auto_emitted:
            # Exact known value: fill linked data immediately, without waiting for focus loss.
            self._last_auto_emitted = normalized
            self.recordSelected.emit(text.strip())
        elif normalized not in self._known:
            self._last_auto_emitted = ""
        if text.strip() and self.count():
            self.completer().setCompletionPrefix(text)
            popup = self.completer().popup()
            popup.setMinimumWidth(max(self.width(), 320))
            self.completer().complete()

    def _editing_finished(self) -> None:
        if self.is_known_record():
            self.recordSelected.emit(self.currentText().strip())

    def _completion_selected(self, text: str) -> None:
        self.setCurrentText(text)
        self.recordSelected.emit(text)

    def _update_record_state(self, text: str) -> None:
        normalized = self._normal(text)
        state = "empty" if not normalized else ("known" if normalized in self._known else "new")
        if self.property("recordState") != state:
            self.setProperty("recordState", state)
            self.style().unpolish(self)
            self.style().polish(self)
        if state == "known":
            self.setToolTip("Ten wpis istnieje już w bazie.")
        elif state == "new":
            self.setToolTip("Nowy wpis - zostanie dodany do bazy podczas zapisu zamówienia.")
        else:
            self.setToolTip("Zacznij pisać, aby zobaczyć wcześniejsze wpisy z bazy.")


class PlaceEditor(QWidget):
    """Pole miejsca z niezależną nazwą i adresem oraz bezpiecznymi podpowiedziami.

    Krytyczna zasada: podczas pisania NIE wolno przebudowywać samego pola tekstowego
    ani automatycznie zatwierdzać pierwszego rekordu. Wartość z bazy trafia do pól
    wyłącznie po świadomym kliknięciu podpowiedzi albo po nawigacji strzałkami.
    """

    recordSelected = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None, placeholder: str = ""):
        super().__init__(parent)
        self.setProperty("overlayField", True)
        self._records: list[Dict[str, str]] = []
        self._search_provider: Optional[Callable[[str], Iterable[Dict[str, Any]]]] = None
        self._setting = False
        self._label_records: Dict[str, Dict[str, str]] = {}
        self._typed_before_popup = ""
        self._user_navigated_popup = False

        lines = str(placeholder or "").splitlines()
        name_placeholder = lines[0] if lines else "Nazwa firmy lub osoby"
        address_placeholder = lines[1] if len(lines) > 1 else "Pełny adres"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Zwykły QLineEdit pozostaje cały czas tym samym obiektem. Poprzedni
        # hotfix czyścił QComboBox przy każdym znaku, przez co Windows tracił fokus.
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText(name_placeholder)
        self.name_edit.setProperty("overlayField", True)
        self.name_edit.setClearButtonEnabled(False)
        self.name_edit.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(self.name_edit, 0)

        self.address_edit = QPlainTextEdit(self)
        self.address_edit.setPlaceholderText(address_placeholder)
        self.address_edit.setProperty("overlayField", True)
        self.address_edit.setFocusPolicy(Qt.StrongFocus)
        self.address_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.address_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.address_edit.document().setDocumentMargin(3)
        layout.addWidget(self.address_edit, 1)

        self._completion_model = QStringListModel(self)
        self._completer = QCompleter(self._completion_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._completer.setMaxVisibleItems(12)
        self._completer.setWrapAround(False)
        self.name_edit.setCompleter(self._completer)
        self._completer.popup().installEventFilter(self)
        self._completer.popup().viewport().installEventFilter(self)
        self.name_edit.installEventFilter(self)
        try:
            self._completer.activated[str].connect(self._completion_activated)
        except (TypeError, KeyError):
            self._completer.activated.connect(self._completion_activated)

        # textEdited reaguje wyłącznie na rzeczywiste pisanie użytkownika.
        self.name_edit.textEdited.connect(self._on_name_edited)
        self.name_edit.returnPressed.connect(self._on_name_return)
        self.name_edit.textChanged.connect(self._refresh_record_state)
        self.address_edit.textChanged.connect(self._refresh_record_state)
        self.setFocusProxy(self.name_edit)
        self._set_record_state("empty")

    @staticmethod
    def _normal(value: str) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    @staticmethod
    def _block(name: str, address: str) -> str:
        name = str(name or "").strip()
        address = str(address or "").strip()
        return f"{name}\n{address}" if name and address else (name or address)

    @staticmethod
    def _split_name_address(name: Any, address: Any) -> tuple[str, str]:
        """Rozdziela starsze rekordy, w których nazwa i adres zapisano razem."""
        raw_name = str(name or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        raw_address = str(address or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        name_lines = [line.strip() for line in raw_name.split("\n") if line.strip()]
        if len(name_lines) > 1:
            raw_name = name_lines[0]
            extra = "\n".join(name_lines[1:])
            if not raw_address:
                raw_address = extra
            elif extra and extra.casefold() not in raw_address.casefold():
                raw_address = f"{extra}\n{raw_address}"
        if not raw_address and "  -  " in raw_name:
            left, right = raw_name.split("  -  ", 1)
            if left.strip() and right.strip():
                raw_name, raw_address = left.strip(), right.strip()
        return raw_name.strip(), raw_address.strip()

    def parts(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self.address_edit.toPlainText().strip()

    def text(self) -> str:
        return self._block(*self.parts()).strip()

    def set_text(self, value: Any) -> None:
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        name = lines[0].strip() if lines else ""
        address = "\n".join(line.strip() for line in lines[1:] if line.strip()).strip()
        self.set_place(name, address, emit=False)

    def set_place(self, name: Any, address: Any, emit: bool = False) -> None:
        clean_name, clean_address = self._split_name_address(name, address)
        self._setting = True
        try:
            self.name_edit.setText(clean_name)
            self.address_edit.setPlainText(clean_address)
            cursor = self.address_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.address_edit.setTextCursor(cursor)
        finally:
            self._setting = False
        self._completer.popup().hide()
        self._user_navigated_popup = False
        self._refresh_record_state()
        if emit:
            self.recordSelected.emit(*self.parts())

    def set_records(self, rows: Iterable[Dict[str, Any]]) -> None:
        records: list[Dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            name, address = self._split_name_address(row.get("name", ""), row.get("address", ""))
            key = (self._normal(name), self._normal(address))
            if name and key not in seen:
                records.append({"name": name, "address": address})
                seen.add(key)
        self._records = records
        self._refresh_record_state()

    def set_search_provider(self, provider: Callable[[str], Iterable[Dict[str, Any]]]) -> None:
        self._search_provider = provider

    def _records_from_provider(self, query: str) -> list[Dict[str, str]]:
        if self._search_provider is None:
            return []
        try:
            rows = self._search_provider(query)
        except Exception as exc:
            self.setToolTip(f"Nie udało się pobrać podpowiedzi z bazy: {exc}")
            return []
        result: list[Dict[str, str]] = []
        for row in rows:
            name, address = self._split_name_address(row.get("name", ""), row.get("address", ""))
            if name:
                result.append({"name": name, "address": address})
        return result

    def _matching_records(self, query: str) -> list[Dict[str, str]]:
        needle = self._normal(query)
        if not needle:
            return []
        live = self._records_from_provider(query)
        sources = live if live else self._records
        starts: list[Dict[str, str]] = []
        word_starts: list[Dict[str, str]] = []
        contains: list[Dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for record in sources:
            name = self._normal(record.get("name", ""))
            address = self._normal(record.get("address", ""))
            key = (name, address)
            if not name or key in seen:
                continue
            seen.add(key)
            if name.startswith(needle):
                starts.append(record)
            elif any(word.startswith(needle) for word in name.split()):
                word_starts.append(record)
            elif needle in name or needle in address:
                contains.append(record)
        return (starts + word_starts + contains)[:12]

    @staticmethod
    def _suggestion_label(record: Dict[str, str]) -> str:
        name = str(record.get("name", "") or "").strip()
        address = " ".join(str(record.get("address", "") or "").split())
        return f"{name}  —  {address}" if address else name

    def _show_matches(self, matches: list[Dict[str, str]], typed_text: str) -> None:
        self._label_records = {}
        labels: list[str] = []
        for record in matches:
            label = self._suggestion_label(record)
            candidate = label
            counter = 2
            while candidate in self._label_records:
                candidate = f"{label} ({counter})"
                counter += 1
            labels.append(candidate)
            self._label_records[candidate] = record

        self._completion_model.setStringList(labels)
        self._typed_before_popup = typed_text
        self._user_navigated_popup = False
        popup = self._completer.popup()
        if not labels:
            popup.hide()
            return

        popup.setMinimumWidth(max(520, self.width()))
        popup.setMaximumHeight(320)
        self._completer.setCompletionPrefix("")
        self._completer.complete()
        # Qt potrafi sam ustawić pierwszy currentIndex. Czyścimy go, aby Enter
        # ani samo kliknięcie pola nie wybierały automatycznie starego rekordu.
        if popup.selectionModel():
            popup.selectionModel().clearSelection()
        popup.setCurrentIndex(QModelIndex())

    def _on_name_edited(self, text: str) -> None:
        if self._setting:
            return
        self._refresh_record_state()
        query = text.strip()
        if not query:
            self._completion_model.setStringList([])
            self._completer.popup().hide()
            return
        self._show_matches(self._matching_records(query), text)

    def eventFilter(self, watched: Any, event: Any) -> bool:  # type: ignore[override]
        popup = self._completer.popup()
        if watched in (popup, popup.viewport(), self.name_edit):
            if event.type() == QEvent.MouseButtonPress and watched in (popup, popup.viewport()):
                self._user_navigated_popup = True
            elif event.type() == QEvent.KeyPress and popup.isVisible() and event.key() in {
                Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown,
                Qt.Key_Home, Qt.Key_End,
            }:
                self._user_navigated_popup = True
        return super().eventFilter(watched, event)

    def _completion_activated(self, value: Any) -> None:
        label = str(value.data() if hasattr(value, "data") else value or "")
        record = self._label_records.get(label)
        if not self._user_navigated_popup or not record:
            # Zabezpieczenie przed automatycznym activation pierwszego wiersza.
            if self.name_edit.text() != self._typed_before_popup:
                self._setting = True
                try:
                    self.name_edit.setText(self._typed_before_popup)
                    self.name_edit.setCursorPosition(len(self._typed_before_popup))
                finally:
                    self._setting = False
            self._completer.popup().hide()
            return
        self.set_place(record.get("name", ""), record.get("address", ""), emit=True)
        self.address_edit.setFocus()

    def _on_name_return(self) -> None:
        popup = self._completer.popup()
        selected = popup.selectionModel().selectedIndexes() if popup.selectionModel() else []
        if popup.isVisible() and self._user_navigated_popup and selected:
            label = str(selected[0].data() or "")
            record = self._label_records.get(label)
            if record:
                self.set_place(record.get("name", ""), record.get("address", ""), emit=True)
                self.address_edit.setFocus()
                return
        popup.hide()
        # Enter bez świadomego wyboru nigdy nie wstawia starego rekordu.
        self.address_edit.setFocus()

    def _exact_pair_exists(self, name: str, address: str) -> bool:
        key = (self._normal(name), self._normal(address))
        return any(
            (self._normal(row.get("name", "")), self._normal(row.get("address", ""))) == key
            for row in self._records
        )

    def _set_record_state(self, state: str) -> None:
        for widget in (self.name_edit, self.address_edit):
            if widget.property("recordState") != state:
                widget.setProperty("recordState", state)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        if state == "known":
            tip = "Ta dokładna nazwa i adres istnieją już w bazie."
        elif state == "new":
            tip = "Nowa nazwa lub nowy adres - wpis zostanie dodany do bazy przy zapisie."
        else:
            tip = "Wpisz pierwsze litery nazwy. Kliknij podpowiedź, aby uzupełnić nazwę i adres."
        self.setToolTip(tip)
        self.name_edit.setToolTip(tip)
        self.address_edit.setToolTip(tip)

    def _refresh_record_state(self) -> None:
        if self._setting:
            return
        name, address = self.parts()
        if not name and not address:
            self._set_record_state("empty")
        elif self._exact_pair_exists(name, address):
            self._set_record_state("known")
        else:
            self._set_record_state("new")

class PdfFormCanvas(QWidget):
    """Original PDF page with real Qt inputs placed over its blank rubrics."""

    PAGE_WIDTH = 595.0
    PAGE_HEIGHT = 842.0

    def __init__(self, template_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.template_path = template_path
        self.zoom = 1.50
        self._controls: list[tuple[QWidget, QRectF]] = []
        self._labels: list[tuple[QWidget, QRectF]] = []
        self._background = self._render_template()
        self.setObjectName("pdfCanvas")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._build_fields()
        self.set_zoom(self.zoom)

    def _render_template(self) -> QPixmap:
        document = fitz.open(self.template_path)
        try:
            page = document[0]
            self.PAGE_WIDTH = float(page.rect.width)
            self.PAGE_HEIGHT = float(page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.8, 2.8), alpha=False)
            image = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format_RGB888,
            ).copy()
            return QPixmap.fromImage(image)
        finally:
            document.close()

    def _combo(self, placeholder: str = "") -> SmartCombo:
        widget = SmartCombo(self, placeholder)
        return widget

    def _place_editor(self, placeholder: str = "") -> PlaceEditor:
        return PlaceEditor(self, placeholder)

    def _add(self, widget: QWidget, rect: tuple[float, float, float, float]) -> QWidget:
        self._controls.append((widget, QRectF(*rect)))
        widget.show()
        return widget

    def _add_label(self, text: str, rect: tuple[float, float, float, float]) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("numberSeparator")
        label.setAlignment(Qt.AlignCenter)
        self._labels.append((label, QRectF(*rect)))
        label.show()
        return label

    def _build_fields(self) -> None:
        self.order_date = QDateEdit(QDate.currentDate(), self)
        self.order_date.setCalendarPopup(True)
        self.order_date.setDisplayFormat("dd.MM.yyyy")
        self.order_date.setProperty("overlayField", True)
        self._add(self.order_date, (488, 103.5, 79, 17))

        self.order_ordinal = QSpinBox(self)
        self.order_ordinal.setRange(1, 99999)
        self.order_ordinal.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.order_ordinal.setAlignment(Qt.AlignCenter)
        self.order_ordinal.setProperty("overlayField", True)
        self._add(self.order_ordinal, (365, 124, 46, 20))
        self._add_label("/", (411, 124, 9, 20))

        self.order_month = QSpinBox(self)
        self.order_month.setRange(1, 12)
        self.order_month.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.order_month.setAlignment(Qt.AlignCenter)
        self.order_month.setProperty("overlayField", True)
        self._add(self.order_month, (420, 124, 29, 20))
        self._add_label("/UT/", (449, 124, 32, 20))

        self.order_year = QSpinBox(self)
        self.order_year.setRange(2020, 2100)
        self.order_year.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.order_year.setAlignment(Qt.AlignCenter)
        self.order_year.setProperty("overlayField", True)
        self._add(self.order_year, (481, 124, 52, 20))

        # Pole "Do" zawiera wyłącznie nazwę przewoźnika. Adres, NIP i pozostałe
        # szczegóły nie są potrzebne na zleceniu.
        self.carrier_name = self._add(self._combo("Nazwa przewoźnika"), (59, 149, 500, 24))

        self.load_date = self._add(self._combo("04.08.2026 / 05.08.2026"), (205, 177, 210, 19))
        self.load_place = self._add(
            self._place_editor("Nazwa firmy lub osoby\nPełny adres załadunku"),
            (42, 198, 510, 52),
        )

        self.unload_date = self._add(self._combo("05.08.2026 / 06.08.2026"), (210, 255, 220, 19))
        self.unload_place = self._add(
            self._place_editor("Nazwa firmy lub osoby\nPełny adres rozładunku"),
            (42, 276, 510, 46),
        )

        self.service_value = self._add(self._combo("np. 2 500 zł netto"), (143, 325, 417, 18))
        self.payment = self._add(self._combo("np. 30 dni przelew"), (103, 341, 457, 18))
        self.cargo_type = self._add(self._combo("Rodzaj ładunku"), (205, 357, 270, 18))
        self.cargo_tons = self._add(self._combo("tony"), (479, 357, 81, 18))

        self.driver_full_name = self._add(self._combo("Imię i nazwisko kierowcy"), (130, 391, 430, 18))
        self.driver_id_card = self._add(self._combo("Seria i numer dowodu"), (145, 415, 415, 18))
        self.driver_pesel = self._add(self._combo("PESEL"), (102, 439, 458, 18))
        self.truck_registration = self._add(self._combo("Rejestracja pojazdu"), (165, 463, 395, 18))
        self.trailer_registration = self._add(self._combo("Rejestracja naczepy"), (170, 487, 390, 18))
        self.driver_phone = self._add(self._combo("Numer telefonu"), (122, 511, 438, 18))

        self.smart_fields: list[SmartCombo] = [
            self.carrier_name,
            self.load_date,
            self.load_place,
            self.unload_date,
            self.unload_place,
            self.service_value,
            self.payment,
            self.cargo_type,
            self.cargo_tons,
            self.driver_full_name,
            self.driver_id_card,
            self.driver_pesel,
            self.truck_registration,
            self.trailer_registration,
            self.driver_phone,
        ]

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(1.10, min(2.10, float(zoom)))
        width = int(round(self.PAGE_WIDTH * self.zoom))
        height = int(round(self.PAGE_HEIGHT * self.zoom))
        self.setFixedSize(width, height)
        for widget, rect in self._controls + self._labels:
            widget.setGeometry(
                int(round(rect.x() * self.zoom)),
                int(round(rect.y() * self.zoom)),
                max(1, int(round(rect.width() * self.zoom))),
                max(1, int(round(rect.height() * self.zoom))),
            )
            font = widget.font()
            font.setPointSizeF(max(7.0, 7.2 * self.zoom / 1.50))
            # All values entered by the user are intentionally bold, both on the
            # on-screen document and in the generated PDF.
            font.setBold(True)
            widget.setFont(font)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), Qt.white)
        painter.drawPixmap(self.rect(), self._background)
        painter.end()


class DriverPasteDialog(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Wklej dane kierowcy z czatu")
        self.resize(640, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Wklej całą wiadomość z danymi kierowcy. Program spróbuje rozpoznać pola automatycznie."))
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Jan Kowalski\nDowód: ABC123456\nPESEL: 90010112345\nAuto: RTA12345\nNaczepa: RTA54321\nTel. 500 600 700"
        )
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Rozpoznaj i wstaw")
        buttons.button(QDialogButtonBox.Cancel).setText("Anuluj")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class DatabaseEditDialog(QDialog):
    """Edit one dictionary record without opening an external database tool."""

    def __init__(
        self,
        category: str,
        row: Dict[str, Any],
        carrier_names: Iterable[str],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.category = category
        self.setWindowTitle("Edycja wpisu w bazie danych")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.fields: Dict[str, QWidget] = {}

        def line(key: str, label: str, value: Any = "") -> QLineEdit:
            editor = QLineEdit(str(value or ""))
            editor.setMinimumHeight(32)
            form.addRow(label, editor)
            self.fields[key] = editor
            return editor

        if category in ("loading", "client"):
            line("name", "Nazwa:", row.get("name", ""))
            address = QPlainTextEdit(str(row.get("address", "") or ""))
            address.setMinimumHeight(120)
            form.addRow("Dokładny adres:", address)
            self.fields["address"] = address
        elif category == "carrier":
            line("name", "Nazwa przewoźnika:", row.get("name", ""))
        elif category == "driver":
            line("full_name", "Imię i nazwisko:", row.get("full_name", ""))
            carrier = QComboBox()
            carrier.setEditable(True)
            names = [str(name or "").strip() for name in carrier_names if str(name or "").strip()]
            carrier.addItems(names)
            carrier.setCurrentText(str(row.get("carrier_name", "") or ""))
            carrier.setMinimumHeight(32)
            form.addRow("Przewoźnik:", carrier)
            self.fields["carrier_name"] = carrier
            line("id_card", "Seria i numer dowodu:", row.get("id_card", ""))
            line("pesel", "PESEL:", row.get("pesel", ""))
            line("truck_registration", "Rejestracja pojazdu:", row.get("truck_registration", ""))
            line("trailer_registration", "Rejestracja naczepy:", row.get("trailer_registration", ""))
            line("phone", "Telefon:", row.get("phone", ""))
        else:
            raise ValueError(f"Nieobsługiwana kategoria: {category}")

        layout.addLayout(form)
        hint = QLabel("Po zapisaniu zmiany podpowiedzi w formularzu zostaną odświeżone automatycznie.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#52616b;")
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Zapisz zmiany")
        buttons.button(QDialogButtonBox.Cancel).setText("Anuluj")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                result[key] = widget.text().strip()
            elif isinstance(widget, QPlainTextEdit):
                result[key] = widget.toPlainText().strip()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText().strip()
        return result

    def _accept_if_valid(self) -> None:
        values = self.values()
        required_key = "full_name" if self.category == "driver" else "name"
        if not values.get(required_key, "").strip():
            QMessageBox.warning(self, "Brak danych", "Nazwa nie może być pusta.")
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TransportDesk | DEMO" if os.environ.get("TRANSPORT_DEMO_MODE") == "1" else "Zamówienia transportowe - edytor dokumentu v4.4 DESKTOP")
        screen = QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.resize(min(1600, int(area.width() * 0.94)), min(1000, int(area.height() * 0.94)))
        else:
            self.resize(1350, 900)
        self.setMinimumSize(980, 600) if os.environ.get("TRANSPORT_DEMO_MODE") == "1" else self.setMinimumSize(1050, 700)

        self.db = Database(CONFIG_PATH)
        self.pdf = PdfGenerator(CONFIG_PATH)
        self.current_order_id: Optional[int] = None
        self.last_pdf_path: Optional[Path] = None

        self._build_ui()
        self._connect_signals()
        self.refresh_dictionaries()
        self.new_order()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_order_tab(), "Zamówienie")
        self.tabs.addTab(self._build_history_tab(), "Historia")
        self.tabs.addTab(self._build_dictionary_tab(), "Baza danych")
        self.statusBar().showMessage("Gotowe")

    def _build_order_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(10, 7, 10, 7)
        bar.setSpacing(7)

        new_btn = QPushButton("Nowe")
        save_btn = QPushButton("Zapisz")
        pdf_btn = QPushButton("Zapisz i utwórz PDF")
        pdf_btn.setObjectName("primary")
        open_btn = QPushButton("Otwórz PDF")
        folder_btn = QPushButton("Folder ZAMÓWIENIA")
        folder_btn.setToolTip("Otwórz folder na pulpicie, w którym zapisywane są wszystkie PDF-y")
        print_btn = QPushButton("Drukuj")
        paste_btn = QPushButton("Wklej dane kierowcy")
        self.note_btn = QToolButton()
        self.note_btn.setText("Notatka wewnętrzna")
        self.note_btn.setCheckable(True)

        new_btn.clicked.connect(self.new_order)
        save_btn.clicked.connect(lambda: self.save_order(False))
        pdf_btn.clicked.connect(lambda: self.save_order(True))
        open_btn.clicked.connect(self.open_last_pdf)
        folder_btn.clicked.connect(self.open_output_folder)
        print_btn.clicked.connect(self.print_current)
        paste_btn.clicked.connect(self.open_driver_paste)
        self.note_btn.toggled.connect(self._toggle_notes)

        for button in (new_btn, save_btn, pdf_btn, open_btn, folder_btn, print_btn, paste_btn, self.note_btn):
            bar.addWidget(button)

        bar.addStretch(1)
        legend = QLabel("zielone = wpis z bazy   •   żółte = nowy wpis")
        legend.setStyleSheet("color:#52616b; font-size:9pt;")
        bar.addWidget(legend)
        self.suggestions_info = QLabel("Podpowiedzi v4.4 DESKTOP")
        self.suggestions_info.setStyleSheet(
            "color:#176c2b; background:#e8f5eb; border:1px solid #6aa777; "
            "border-radius:3px; padding:3px 7px; font-weight:700;"
        )
        bar.addWidget(self.suggestions_info)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Skala:"))
        self.zoom_levels = [1.25, 1.40, 1.50, 1.60, 1.75]
        self.zoom_index = 2
        zoom_minus = QToolButton()
        zoom_minus.setText("-")
        zoom_minus.setToolTip("Zmniejsz dokument")
        zoom_minus.setFixedWidth(32)
        zoom_minus.clicked.connect(self._zoom_out)
        self.zoom_value = QLabel("150%")
        self.zoom_value.setAlignment(Qt.AlignCenter)
        self.zoom_value.setMinimumWidth(56)
        self.zoom_value.setStyleSheet("font-weight:700; color:#17212b; background:#ffffff; border:1px solid #9da7af; border-radius:4px; padding:5px;")
        zoom_plus = QToolButton()
        zoom_plus.setText("+")
        zoom_plus.setToolTip("Powiększ dokument")
        zoom_plus.setFixedWidth(32)
        zoom_plus.clicked.connect(self._zoom_in)
        bar.addWidget(zoom_minus)
        bar.addWidget(self.zoom_value)
        bar.addWidget(zoom_plus)
        layout.addWidget(toolbar)

        self.notes_panel = QFrame()
        self.notes_panel.setObjectName("notesPanel")
        notes_layout = QVBoxLayout(self.notes_panel)
        notes_layout.setContentsMargins(12, 8, 12, 10)
        notes_layout.addWidget(QLabel("Notatka wewnętrzna - nie trafia do PDF ani na wydruk:"))
        self.internal_notes = QPlainTextEdit()
        self.internal_notes.setMaximumHeight(76)
        self.internal_notes.setPlaceholderText("Opcjonalna informacja widoczna tylko w aplikacji.")
        notes_layout.addWidget(self.internal_notes)
        self.notes_panel.setVisible(False)
        layout.addWidget(self.notes_panel)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(20, 18, 20, 25)
        scroll_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        template_path = APP_ROOT / "assets" / "template.pdf"
        self.canvas = PdfFormCanvas(template_path)
        scroll_layout.addWidget(self.canvas, 0, Qt.AlignHCenter | Qt.AlignTop)
        self.scroll.setWidget(scroll_content)
        layout.addWidget(self.scroll, 1)
        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        buttons = QHBoxLayout()
        refresh = QPushButton("Odśwież")
        load = QPushButton("Wczytaj do dokumentu")
        open_pdf = QPushButton("Otwórz PDF")
        delete_order = QPushButton("Usuń zamówienie")
        delete_order.setObjectName("historyDelete")
        refresh.clicked.connect(self.refresh_history)
        load.clicked.connect(self.load_selected_order)
        open_pdf.clicked.connect(self.open_selected_pdf)
        delete_order.clicked.connect(self.delete_selected_order)
        buttons.addWidget(refresh)
        buttons.addWidget(load)
        buttons.addWidget(open_pdf)
        buttons.addWidget(delete_order)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.history_table = QTableWidget(0, 9)
        self.history_table.setHorizontalHeaderLabels([
            "ID", "Numer", "Data", "Przewoźnik", "Załadunek", "Rozładunek", "Wartość", "PDF", "Usuń"
        ])
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.doubleClicked.connect(self.load_selected_order)
        layout.addWidget(self.history_table)
        return page

    def _build_dictionary_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.dictionary_category = QComboBox()
        self.dictionary_category.addItem("Miejsca załadunku", "loading")
        self.dictionary_category.addItem("Klienci / rozładunki", "client")
        self.dictionary_category.addItem("Przewoźnicy", "carrier")
        self.dictionary_category.addItem("Kierowcy", "driver")
        refresh = QPushButton("Odśwież")
        edit = QPushButton("Edytuj zaznaczony wpis")
        edit.setObjectName("primary")
        delete = QPushButton("Usuń zaznaczony wpis")
        refresh.clicked.connect(self.refresh_dictionary_table)
        edit.clicked.connect(self.edit_dictionary_row)
        delete.clicked.connect(self.delete_dictionary_row)
        self.dictionary_category.currentIndexChanged.connect(self.refresh_dictionary_table)
        top.addWidget(QLabel("Pokaż:"))
        top.addWidget(self.dictionary_category)
        top.addWidget(refresh)
        top.addWidget(edit)
        top.addWidget(delete)
        top.addStretch()
        layout.addLayout(top)
        layout.addWidget(QLabel("Wpisy są dodawane automatycznie. Zaznacz wiersz i kliknij Edytuj albo kliknij go dwukrotnie."))
        self.dictionary_table = QTableWidget()
        self.dictionary_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dictionary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dictionary_table.doubleClicked.connect(self.edit_dictionary_row)
        self.dictionary_table.setAlternatingRowColors(True)
        self.dictionary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.dictionary_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.dictionary_table)
        return page

    def _connect_signals(self) -> None:
        for widget in (self.canvas.order_ordinal, self.canvas.order_month, self.canvas.order_year):
            widget.valueChanged.connect(self._number_changed)
        self.canvas.order_date.dateChanged.connect(self._date_changed)

        self.canvas.carrier_name.recordSelected.connect(lambda _: self.fill_carrier())
        self.canvas.load_place.recordSelected.connect(
            lambda name, address: self.statusBar().showMessage(f"Wybrano załadunek: {name}")
        )
        self.canvas.unload_place.recordSelected.connect(
            lambda name, address: self.statusBar().showMessage(f"Wybrano rozładunek: {name}")
        )
        self.canvas.driver_full_name.recordSelected.connect(lambda _: self.fill_driver())

        # Live suggestions are fetched directly from the database on every
        # keystroke. This works even when the dictionaries were not refreshed.
        self.canvas.load_place.set_search_provider(
            lambda query: self.db.search_places("loading", query, limit=12)
        )
        self.canvas.unload_place.set_search_provider(
            lambda query: self.db.search_places("client", query, limit=12)
        )

    def _apply_zoom(self) -> None:
        self.zoom_index = max(0, min(self.zoom_index, len(self.zoom_levels) - 1))
        zoom = self.zoom_levels[self.zoom_index]
        self.canvas.set_zoom(zoom)
        self.zoom_value.setText(f"{round(zoom * 100):.0f}%")

    def _zoom_out(self) -> None:
        if self.zoom_index > 0:
            self.zoom_index -= 1
            self._apply_zoom()

    def _zoom_in(self) -> None:
        if self.zoom_index < len(self.zoom_levels) - 1:
            self.zoom_index += 1
            self._apply_zoom()

    def _toggle_notes(self, checked: bool) -> None:
        self.notes_panel.setVisible(checked)
        if checked:
            self.internal_notes.setFocus()

    def _number_changed(self) -> None:
        self.last_pdf_path = None

    def _date_changed(self, date: QDate) -> None:
        if self.current_order_id is None:
            self.canvas.order_month.setValue(date.month())
            self.canvas.order_year.setValue(date.year())
            self.canvas.order_ordinal.setValue(self.db.next_order_ordinal(date.month(), date.year()))

    def order_number(self) -> str:
        return (
            f"{self.canvas.order_ordinal.value()}/"
            f"{self.canvas.order_month.value():02d}/UT/"
            f"{self.canvas.order_year.value()}"
        )

    @staticmethod
    def _merge_values(*groups: Iterable[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for value in group:
                text = str(value or "").strip()
                key = " ".join(text.casefold().split())
                if text and key not in seen:
                    result.append(text)
                    seen.add(key)
        return result

    def refresh_dictionaries(self) -> None:
        carriers = self.db.list_carriers()
        # search_places merges the dedicated dictionary with historical orders.
        loading = list(self.db.search_places("loading", "", limit=2000))
        clients = list(self.db.search_places("client", "", limit=2000))
        drivers = self.db.list_drivers()

        distinct = self.db.distinct_order_values
        self.canvas.carrier_name.set_values(
            self._merge_values((row.get("name", "") for row in carriers), distinct("carrier_name"))
        )
        self.canvas.load_place.set_records(loading)
        self.canvas.load_date.set_values(distinct("load_date"))
        self.canvas.unload_place.set_records(clients)
        self.canvas.unload_date.set_values(distinct("unload_date"))
        self.canvas.service_value.set_values(distinct("service_value"))
        self.canvas.payment.set_values(self._merge_values(["30 dni przelew", "14 dni przelew", "gotówka"], distinct("payment")))
        self.canvas.cargo_type.set_values(self._merge_values(["Nawozy mineralne"], distinct("cargo_type")))
        self.canvas.cargo_tons.set_values(distinct("cargo_tons"))

        self.canvas.driver_full_name.set_values(
            self._merge_values((row.get("full_name", "") for row in drivers), distinct("driver_full_name"))
        )
        self.canvas.driver_id_card.set_values(
            self._merge_values((row.get("id_card", "") for row in drivers), distinct("driver_id_card"))
        )
        self.canvas.driver_pesel.set_values(
            self._merge_values((row.get("pesel", "") for row in drivers), distinct("driver_pesel"))
        )
        self.canvas.truck_registration.set_values(
            self._merge_values((row.get("truck_registration", "") for row in drivers), distinct("truck_registration"))
        )
        self.canvas.trailer_registration.set_values(
            self._merge_values((row.get("trailer_registration", "") for row in drivers), distinct("trailer_registration"))
        )
        self.canvas.driver_phone.set_values(
            self._merge_values((row.get("phone", "") for row in drivers), distinct("driver_phone"))
        )
        self.refresh_history()
        self.refresh_dictionary_table()
        info = f"LIVE: {len(loading)} załadunków / {len(clients)} rozładunków"
        self.suggestions_info.setText(info)
        self.suggestions_info.setToolTip(f"Używana baza: {self.db.database_location}")
        self.statusBar().showMessage(
            f"Podpowiedzi {info}. Baza: {self.db.database_location}",
            12000,
        )

    def refresh_driver_names_for_carrier(self) -> None:
        # Driver names are assumed unique, so suggestions are always global.
        current = self.canvas.driver_full_name.text()
        drivers = self.db.list_drivers()
        self.canvas.driver_full_name.set_values(
            self._merge_values((row.get("full_name", "") for row in drivers), self.db.distinct_order_values("driver_full_name"))
        )
        self.canvas.driver_full_name.set_text(current)

    def fill_carrier(self) -> None:
        # Nazwa przewoźnika jest jedyną informacją drukowaną w polu "Do".
        self.refresh_driver_names_for_carrier()

    def fill_driver(self) -> None:
        # Full name is treated as the unique driver key.
        row = self.db.get_driver(self.canvas.driver_full_name.text())
        if row:
            self.canvas.driver_id_card.set_text(row.get("id_card", ""))
            self.canvas.driver_pesel.set_text(row.get("pesel", ""))
            self.canvas.truck_registration.set_text(row.get("truck_registration", ""))
            self.canvas.trailer_registration.set_text(row.get("trailer_registration", ""))
            self.canvas.driver_phone.set_text(row.get("phone", ""))

    def open_driver_paste(self) -> None:
        dialog = DriverPasteDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        parsed = parse_driver_text(dialog.editor.toPlainText())
        mapping = {
            "full_name": self.canvas.driver_full_name,
            "id_card": self.canvas.driver_id_card,
            "pesel": self.canvas.driver_pesel,
            "truck_registration": self.canvas.truck_registration,
            "trailer_registration": self.canvas.trailer_registration,
            "phone": self.canvas.driver_phone,
        }
        recognized = 0
        for key, widget in mapping.items():
            value = parsed.get(key, "")
            if value:
                widget.set_text(value)
                recognized += 1
        self.statusBar().showMessage(f"Rozpoznano {recognized} pól z wiadomości kierowcy")

    def new_order(self) -> None:
        self.current_order_id = None
        self.last_pdf_path = None
        today = QDate.currentDate()
        self.canvas.order_date.setDate(today)
        self.canvas.order_month.setValue(today.month())
        self.canvas.order_year.setValue(today.year())
        self.canvas.order_ordinal.setValue(self.db.next_order_ordinal(today.month(), today.year()))
        for field in self.canvas.smart_fields:
            field.set_text("")
        today_text = today.toString("dd.MM.yyyy")
        self.canvas.load_date.set_text(today_text)
        self.canvas.unload_date.set_text(today_text)
        self.canvas.payment.set_text("30 dni przelew")
        self.canvas.cargo_type.set_text("Nawozy mineralne")
        self.internal_notes.clear()
        self.note_btn.setChecked(False)
        self.notes_panel.setVisible(False)
        self.tabs.setCurrentIndex(0)
        self.scroll.verticalScrollBar().setValue(0)
        self.statusBar().showMessage(f"Nowe zamówienie {self.order_number()}")

    @staticmethod
    def _iso(date_edit: QDateEdit) -> str:
        return date_edit.date().toString("yyyy-MM-dd")

    @staticmethod
    def _display_date_text(value: Any) -> str:
        text = str(value or "").strip()
        return re.sub(
            r"\b(\d{4})-(\d{2})-(\d{2})\b",
            lambda match: f"{match.group(3)}.{match.group(2)}.{match.group(1)}",
            text,
        )

    @staticmethod
    def _tons_number(text: str) -> float:
        cleaned = str(text or "").strip().replace(" ", "").replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except ValueError:
            return 0.0

    def collect_order(self) -> Dict[str, Any]:
        c = self.canvas
        load_name, load_address = c.load_place.parts()
        unload_name, unload_address = c.unload_place.parts()
        return {
            "order_ordinal": c.order_ordinal.value(),
            "order_month": c.order_month.value(),
            "order_year": c.order_year.value(),
            "order_number": self.order_number(),
            "order_date": self._iso(c.order_date),
            "internal_notes": self.internal_notes.toPlainText().strip(),
            "carrier_name": c.carrier_name.text(),
            "carrier_details": "",
            "load_place_name": load_name,
            "load_address": load_address,
            "load_date": c.load_date.text(),
            "unload_place_name": unload_name,
            "unload_address": unload_address,
            "unload_date": c.unload_date.text(),
            "service_value": c.service_value.text(),
            "payment": c.payment.text(),
            "cargo_type": c.cargo_type.text(),
            "cargo_tons": self._tons_number(c.cargo_tons.text()),
            "driver_full_name": c.driver_full_name.text(),
            "driver_id_card": c.driver_id_card.text(),
            "driver_pesel": c.driver_pesel.text(),
            "truck_registration": c.truck_registration.text().upper(),
            "trailer_registration": c.trailer_registration.text().upper(),
            "driver_phone": c.driver_phone.text(),
            "pdf_path": str(self.last_pdf_path or ""),
        }

    def validate_order(self, order: Dict[str, Any]) -> bool:
        required = {
            "carrier_name": "przewoźnika",
            "load_place_name": "miejsce załadunku",
            "unload_place_name": "klienta / miejsce rozładunku",
            "driver_full_name": "imię i nazwisko kierowcy",
        }
        missing = [label for key, label in required.items() if not str(order.get(key, "")).strip()]
        if missing:
            QMessageBox.warning(self, "Brak danych", "Uzupełnij: " + ", ".join(missing) + ".")
            return False
        return True

    def save_dictionary_values(self, order: Dict[str, Any]) -> None:
        carrier_id = self.db.save_carrier(order["carrier_name"])
        self.db.save_place("loading", order["load_place_name"], order["load_address"])
        self.db.save_place("client", order["unload_place_name"], order["unload_address"])
        self.db.save_driver({
            "carrier_name": order["carrier_name"],
            "full_name": order["driver_full_name"],
            "id_card": order["driver_id_card"],
            "pesel": order["driver_pesel"],
            "truck_registration": order["truck_registration"],
            "trailer_registration": order["trailer_registration"],
            "phone": order["driver_phone"],
        }, carrier_id)

    def save_order(self, generate_pdf: bool = False) -> Optional[Path]:
        order = self.collect_order()
        if not self.validate_order(order):
            return None
        try:
            self.save_dictionary_values(order)
            if generate_pdf:
                path = self.pdf.generate(order)
                self.last_pdf_path = path
                order["pdf_path"] = str(path)
            self.current_order_id = self.db.save_order(order)
            self.refresh_dictionaries()
            message = f"Zapisano zamówienie {order['order_number']}"
            if generate_pdf and self.last_pdf_path:
                message += f"\nUtworzono PDF: {self.last_pdf_path}"
            QMessageBox.information(self, "Gotowe", message)
            self.statusBar().showMessage(message.replace("\n", " "))
            return self.last_pdf_path
        except Exception as exc:
            QMessageBox.critical(self, "Błąd zapisu", str(exc))
            return None

    def ensure_pdf(self) -> Optional[Path]:
        if self.last_pdf_path and self.last_pdf_path.exists():
            return self.last_pdf_path
        return self.save_order(generate_pdf=True)

    def open_output_folder(self) -> None:
        try:
            self.pdf.output_dir.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pdf.output_dir.resolve())))
            if not opened:
                QMessageBox.warning(
                    self,
                    "Nie udało się otworzyć folderu",
                    f"Folder istnieje, ale Windows go nie otworzył:\n{self.pdf.output_dir}",
                )
        except Exception as exc:
            QMessageBox.critical(self, "Błąd otwierania folderu", str(exc))

    def open_last_pdf(self) -> None:
        path = self.ensure_pdf()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def print_current(self) -> None:
        path = self.ensure_pdf()
        if not path:
            return
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Drukowanie zamówienia")
        if dialog.exec() != QPrintDialog.Accepted:
            return
        try:
            document = fitz.open(path)
            painter = QPainter(printer)
            for index, page in enumerate(document):
                if index > 0:
                    printer.newPage()
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
                image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                viewport = painter.viewport()
                scaled = image.size().scaled(viewport.size(), Qt.KeepAspectRatio)
                x = viewport.x() + (viewport.width() - scaled.width()) // 2
                y = viewport.y() + (viewport.height() - scaled.height()) // 2
                painter.drawImage(x, y, image.scaled(scaled, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            painter.end()
            document.close()
            self.statusBar().showMessage("Dokument wysłany do drukarki")
        except Exception as exc:
            QMessageBox.critical(self, "Błąd drukowania", str(exc))

    def refresh_history(self) -> None:
        rows = self.db.list_orders()
        self.history_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("id", ""), row.get("order_number", ""), row.get("order_date", ""),
                row.get("carrier_name", ""), row.get("load_place_name", ""), row.get("unload_place_name", ""),
                row.get("service_value", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.history_table.setItem(row_index, column, item)

            order_id = int(row.get("id", 0) or 0)
            pdf_button = QPushButton("Otwórz PDF")
            pdf_button.setObjectName("historyPdf")
            pdf_button.setCursor(Qt.PointingHandCursor)
            pdf_button.setToolTip(
                "Otwórz PDF tego zamówienia. Jeśli plik został przeniesiony lub usunięty, "
                "aplikacja odtworzy go z danych zapisanych w historii."
            )
            pdf_button.clicked.connect(
                lambda checked=False, selected_id=order_id: self.open_pdf_for_order(selected_id)
            )
            self.history_table.setCellWidget(row_index, 7, pdf_button)

            delete_button = QPushButton("Usuń")
            delete_button.setObjectName("historyDelete")
            delete_button.setCursor(Qt.PointingHandCursor)
            delete_button.setToolTip(
                "Usuń całe zamówienie z historii oraz powiązany plik PDF z dysku."
            )
            delete_button.clicked.connect(
                lambda checked=False, selected_id=order_id: self.delete_order(selected_id)
            )
            self.history_table.setCellWidget(row_index, 8, delete_button)

        self.history_table.resizeRowsToContents()
        self.history_table.setColumnWidth(7, 118)
        self.history_table.setColumnWidth(8, 82)

    def selected_history_id(self) -> Optional[int]:
        row = self.history_table.currentRow()
        if row < 0 or not self.history_table.item(row, 0):
            QMessageBox.information(self, "Historia", "Zaznacz zamówienie w tabeli.")
            return None
        return int(self.history_table.item(row, 0).text())

    def load_selected_order(self) -> None:
        order_id = self.selected_history_id()
        if order_id is None:
            return
        order = self.db.get_order(order_id)
        if not order:
            return
        c = self.canvas
        self.current_order_id = order_id
        c.order_ordinal.setValue(int(order["order_ordinal"]))
        c.order_month.setValue(int(order["order_month"]))
        c.order_year.setValue(int(order["order_year"]))
        date = QDate.fromString(str(order.get("order_date", ""))[:10], "yyyy-MM-dd")
        c.order_date.setDate(date if date.isValid() else QDate.currentDate())

        values = {
            c.carrier_name: order.get("carrier_name", ""),
            c.load_date: self._display_date_text(order.get("load_date", "")),
            c.unload_date: self._display_date_text(order.get("unload_date", "")),
            c.service_value: order.get("service_value", ""),
            c.payment: order.get("payment", ""),
            c.cargo_type: order.get("cargo_type", ""),
            c.cargo_tons: str(order.get("cargo_tons", "") or "").replace(".0", ""),
            c.driver_full_name: order.get("driver_full_name", ""),
            c.driver_id_card: order.get("driver_id_card", ""),
            c.driver_pesel: order.get("driver_pesel", ""),
            c.truck_registration: order.get("truck_registration", ""),
            c.trailer_registration: order.get("trailer_registration", ""),
            c.driver_phone: order.get("driver_phone", ""),
        }
        for widget, value in values.items():
            widget.set_text(value)
        c.load_place.set_place(order.get("load_place_name", ""), order.get("load_address", ""))
        c.unload_place.set_place(order.get("unload_place_name", ""), order.get("unload_address", ""))

        note = str(order.get("internal_notes", ""))
        self.internal_notes.setPlainText(note)
        self.note_btn.setChecked(bool(note.strip()))
        self.notes_panel.setVisible(bool(note.strip()))
        pdf_path = str(order.get("pdf_path", ""))
        self.last_pdf_path = Path(pdf_path) if pdf_path else None
        self.tabs.setCurrentIndex(0)
        self.scroll.verticalScrollBar().setValue(0)
        self.statusBar().showMessage(f"Wczytano {order.get('order_number', '')}")

    def _find_existing_pdf(self, order: Dict[str, Any]) -> Optional[Path]:
        stored = str(order.get("pdf_path", "") or "").strip()
        if stored:
            stored_path = Path(stored)
            if stored_path.exists():
                return stored_path

        expected = self.pdf.expected_path(order)
        if expected.exists():
            return expected

        filename = expected.name
        matches = list(self.pdf.output_dir.rglob(filename))
        return matches[0] if matches else None

    def open_pdf_for_order(self, order_id: int) -> None:
        order = self.db.get_order(order_id)
        if not order:
            QMessageBox.information(self, "Historia", "Nie znaleziono tego zamówienia w bazie.")
            return

        try:
            path = self._find_existing_pdf(order)
            if path is None:
                path = self.pdf.generate(order)
                self.db.update_order_pdf_path(order_id, str(path))
                self.refresh_history()

            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
            if not opened:
                QMessageBox.warning(
                    self,
                    "Nie udało się otworzyć PDF",
                    f"Plik został znaleziony, ale Windows nie uruchomił przeglądarki PDF:\n{path}",
                )
                return
            self.statusBar().showMessage(f"Otwarto PDF: {order.get('order_number', '')}")
        except Exception as exc:
            QMessageBox.critical(self, "Błąd otwierania PDF", str(exc))

    def open_selected_pdf(self) -> None:
        order_id = self.selected_history_id()
        if order_id is not None:
            self.open_pdf_for_order(order_id)

    def _order_pdf_candidates(self, order: Dict[str, Any]) -> list[Path]:
        """Return unique PDF files that belong to one order.

        We check both the path saved in the database and the current expected
        output path, so cleanup also works after moving the application folder.
        """
        candidates: list[Path] = []
        stored = str(order.get("pdf_path", "") or "").strip()
        if stored:
            candidates.append(Path(stored))

        expected = self.pdf.expected_path(order)
        candidates.append(expected)

        # Older versions could leave the same PDF in another year/month folder.
        try:
            if self.pdf.output_dir.exists():
                candidates.extend(self.pdf.output_dir.rglob(expected.name))
        except OSError:
            pass

        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                key = str(candidate.resolve()).casefold()
            except OSError:
                key = str(candidate.absolute()).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    def delete_selected_order(self) -> None:
        order_id = self.selected_history_id()
        if order_id is not None:
            self.delete_order(order_id)

    def delete_order(self, order_id: int) -> None:
        order = self.db.get_order(order_id)
        if not order:
            QMessageBox.information(self, "Historia", "Nie znaleziono tego zamówienia w bazie.")
            self.refresh_history()
            return

        order_number = str(order.get("order_number", "") or f"ID {order_id}")
        existing_files = [
            path for path in self._order_pdf_candidates(order)
            if path.suffix.casefold() == ".pdf" and path.is_file()
        ]
        file_note = (
            f"\n\nZostanie też trwale usunięty plik PDF ({len(existing_files)} znaleziony)."
            if len(existing_files) == 1
            else f"\n\nZostaną też trwale usunięte pliki PDF ({len(existing_files)} znalezione)."
            if existing_files
            else "\n\nNie znaleziono powiązanego pliku PDF na dysku."
        )
        answer = QMessageBox.warning(
            self,
            "Usuń całe zamówienie",
            f"Czy na pewno trwale usunąć zamówienie {order_number} z historii?"
            f"{file_note}\n\nTej operacji nie można cofnąć.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        failed: list[str] = []
        deleted_files = 0
        for path in existing_files:
            try:
                path.unlink()
                deleted_files += 1
                # Remove empty month/year directories, but never the PDF root.
                parent = path.parent
                for _ in range(2):
                    if parent == self.pdf.output_dir or not parent.exists():
                        break
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
            except OSError as exc:
                failed.append(f"{path}: {exc}")

        if failed:
            QMessageBox.critical(
                self,
                "Nie usunięto zamówienia",
                "Nie udało się usunąć powiązanego PDF-u. Rekord pozostał w bazie, "
                "żeby historia nie wskazywała na niepełne usunięcie.\n\n"
                + "\n".join(failed),
            )
            return

        try:
            self.db.delete_order(order_id)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Błąd usuwania",
                f"PDF został usunięty, ale nie udało się usunąć rekordu z bazy:\n{exc}",
            )
            return

        if self.current_order_id == order_id:
            self.new_order()
        self.refresh_history()
        self.statusBar().showMessage(
            f"Usunięto zamówienie {order_number} i {deleted_files} plik(ów) PDF.",
            10000,
        )

    def refresh_dictionary_table(self) -> None:
        category = self.dictionary_category.currentData()
        if category in ("loading", "client"):
            rows = self.db.list_places(str(category))
            columns = [("id", "ID"), ("name", "Nazwa"), ("address", "Adres"), ("updated_at", "Aktualizacja")]
        elif category == "carrier":
            rows = self.db.list_carriers()
            columns = [("id", "ID"), ("name", "Nazwa"), ("updated_at", "Aktualizacja")]
        else:
            rows = self.db.list_drivers()
            columns = [
                ("id", "ID"), ("full_name", "Kierowca"), ("carrier_name", "Przewoźnik"),
                ("id_card", "Dowód"), ("pesel", "PESEL"),
                ("truck_registration", "Pojazd"), ("trailer_registration", "Naczepa"),
                ("phone", "Telefon"), ("updated_at", "Aktualizacja"),
            ]
        self.dictionary_table.setColumnCount(len(columns))
        self.dictionary_table.setHorizontalHeaderLabels([label for _, label in columns])
        self.dictionary_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for col, (key, _) in enumerate(columns):
                self.dictionary_table.setItem(r, col, QTableWidgetItem(str(row.get(key, "") or "")))
        self.dictionary_table.resizeRowsToContents()

    def edit_dictionary_row(self, _index: Any = None) -> None:
        row_index = self.dictionary_table.currentRow()
        if row_index < 0 or not self.dictionary_table.item(row_index, 0):
            QMessageBox.information(self, "Baza danych", "Zaznacz wpis, który chcesz edytować.")
            return
        category = str(self.dictionary_category.currentData())
        row_id = int(self.dictionary_table.item(row_index, 0).text())
        try:
            row = self.db.get_dictionary_row(category, row_id)
            if not row:
                QMessageBox.warning(self, "Baza danych", "Nie znaleziono tego wpisu w bazie.")
                self.refresh_dictionary_table()
                return
            carriers = [item.get("name", "") for item in self.db.list_carriers()]
            dialog = DatabaseEditDialog(category, row, carriers, self)
            if dialog.exec() != QDialog.Accepted:
                return
            self.db.update_dictionary_row(category, row_id, dialog.values())
            self.refresh_dictionaries()
            self.dictionary_category.setCurrentIndex(
                max(0, self.dictionary_category.findData(category))
            )
            self.refresh_dictionary_table()
            self.statusBar().showMessage("Zapisano zmiany w bazie danych.", 7000)
        except Exception as exc:
            QMessageBox.critical(self, "Błąd edycji bazy", str(exc))

    def delete_dictionary_row(self) -> None:
        row = self.dictionary_table.currentRow()
        if row < 0 or not self.dictionary_table.item(row, 0):
            QMessageBox.information(self, "Baza danych", "Zaznacz wpis do usunięcia.")
            return
        row_id = int(self.dictionary_table.item(row, 0).text())
        if QMessageBox.question(self, "Potwierdzenie", "Usunąć zaznaczony wpis z bazy?") != QMessageBox.Yes:
            return
        try:
            self.db.delete_dictionary_row(str(self.dictionary_category.currentData()), row_id)
            self.refresh_dictionaries()
        except Exception as exc:
            QMessageBox.critical(self, "Błąd", str(exc))


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Zamówienia transportowe")
    app.setOrganizationName("PortfolioDemo")
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyle("Fusion")
    screen = app.primaryScreen()
    base_size = 10 if not screen or screen.logicalDotsPerInch() < 120 else 11
    app.setFont(QFont("Segoe UI", base_size))

    palette = app.palette()
    palette.setColor(QPalette.Window, QColor("#e7ebef"))
    palette.setColor(QPalette.WindowText, QColor("#17212b"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#111111"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#17212b"))
    palette.setColor(QPalette.Highlight, QColor("#218739"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLE)

    try:
        window = MainWindow()
        if ICON_PATH.exists():
            window.setWindowIcon(QIcon(str(ICON_PATH)))
    except Exception as exc:
        details = traceback.format_exc()
        try:
            (APP_ROOT / "blad_uruchomienia.txt").write_text(details, encoding="utf-8")
        except Exception:
            pass
        QMessageBox.critical(
            None,
            "Błąd uruchomienia",
            f"{exc}\n\nSzczegóły zapisano w pliku blad_uruchomienia.txt.",
        )
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
