"""Start the actual Qt app against an isolated, seeded demonstration database."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from demo.workspace import demo_home, prepare_workspace


def smoke_test(work: Path) -> int:
    """Check packaged Qt interface, sample orders and generated PDFs without a GUI loop."""
    from PySide6.QtWidgets import QApplication
    from main import APP_STYLE, MainWindow

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    try:
        window.show()
        app.processEvents()
        window.refresh_history()
        assert window.history_table.rowCount() >= 2, "Two demo orders were not loaded"
        window.history_table.setCurrentCell(0, 0)
        window.history_table.selectRow(0)
        window.load_selected_order()
        app.processEvents()
        assert window.current_order_id is not None, "Could not reopen a saved order"
        assert window.grab().save(str(work / "smoke-preview.png")), "Cannot render Qt window"
        pdfs = list((work / "output").rglob("*.pdf"))
        assert len(pdfs) >= 2, "Generated sample PDFs are missing"
        (work / "smoke-test.txt").write_text(
            "PASS: Qt window, two orders, PDF output\n", encoding="utf-8"
        )
        return 0
    finally:
        window.close()
        window.db.connection.close()


def run() -> int:
    flags = set(sys.argv[1:])
    work = prepare_workspace(reset="--reset" in flags)
    os.environ["TRANSPORT_APP_ROOT"] = str(work)
    os.environ["TRANSPORT_DEMO_MODE"] = "1"
    sys.path.insert(0, str(PROJECT_ROOT / "app"))
    if "--smoke-test" in flags:
        return smoke_test(work)
    from main import main
    sys.argv = [sys.argv[0]]
    return main()


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        details = traceback.format_exc()
        try:
            home = demo_home()
            home.mkdir(parents=True, exist_ok=True)
            (home / "last_launch_error.txt").write_text(details, encoding="utf-8")
        except Exception:
            pass
        print(details, file=sys.stderr)
        raise SystemExit(1)
