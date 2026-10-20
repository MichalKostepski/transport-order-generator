"""Generate real PySide6 screenshots from fictional records, never company data."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo.workspace import prepare_workspace

def main() -> None:
    work = prepare_workspace(reset=True)
    os.environ["TRANSPORT_APP_ROOT"] = str(work)
    os.environ["TRANSPORT_DEMO_MODE"] = "1"
    sys.path.insert(0, str(ROOT / "app"))
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont, QPalette, QColor, QFontDatabase, QFontMetrics
    from main import MainWindow, APP_STYLE

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    # CI's offscreen Qt plugin may not resolve a system font automatically.
    # Explicitly load Arial from Windows so Polish glyphs render as text,
    # rather than tofu/empty square placeholders.
    preferred_font = "Arial" if sys.platform == "win32" else "DejaVu Sans"
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Fonts"
    arial = fonts_dir / "arial.ttf"
    if sys.platform == "win32" and arial.is_file():
        loaded_id = QFontDatabase.addApplicationFont(str(arial))
        if loaded_id >= 0:
            preferred_font = QFontDatabase.applicationFontFamilies(loaded_id)[0]
    font = QFont(preferred_font, 9)
    app.setFont(font)
    metrics = QFontMetrics(font)
    print(
        "Qt platform:", app.platformName(),
        "font:", font.family(),
        "Arial exists:", arial.is_file(),
        "Latin glyph:", metrics.inFont("A"),
        "Polish glyph:", metrics.inFont("ą"),
        flush=True,
    )
    if not metrics.inFont("A") or not metrics.inFont("ą"):
        print("WARNING: Qt font metrics could not confirm all glyphs; review screenshot manually.", flush=True)
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor("#e7ebef"))
    palette.setColor(QPalette.WindowText, QColor("#17212b"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#111111"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLE)

    output = ROOT / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    window = MainWindow()
    try:
        window.resize(1500, 890)
        window.show()
        app.processEvents()

        window.refresh_history()
        window.tabs.setCurrentIndex(1)
        app.processEvents()
        assert window.history_table.rowCount() == 2, "Expected exactly two fictional orders"
        history_capture = window.grab()
        assert history_capture.copy(0, 0, history_capture.width(), min(310, history_capture.height())).save(str(output / "order-history.png"))

        window.history_table.setCurrentCell(0, 0)
        window.history_table.selectRow(0)
        window.load_selected_order()
        window.note_btn.setChecked(False)
        window.zoom_index = 0  # Show more of the real PDF-aligned editor.
        window._apply_zoom()
        app.processEvents()
        assert window.current_order_id is not None
        assert window.tabs.currentIndex() == 0
        assert window.grab().save(str(output / "pdf-editor.png"))
    finally:
        window.close()
        window.db.connection.close()

    for filename in ("order-history.png", "pdf-editor.png"):
        image = output / filename
        assert image.stat().st_size > 1000, f"Bad screenshot: {image}"
        print(f"Captured {filename}: {image.stat().st_size} bytes (fictional data)")

if __name__ == "__main__":
    main()
