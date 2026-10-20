"""Non-GUI integration test for the isolated demo workspace."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from unicodedata import normalize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from demo.workspace import prepare_workspace
from demo.sample_data import EXAMPLE_MESSAGE
from database import Database
from driver_parser import parse_driver_text
import fitz


def main():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "only_demo"
        os.environ["TRANSPORT_DEMO_HOME"] = str(work)
        # An unrelated file outside the demo workspace must survive resets.
        sentinel = Path(tmp) / "other_company_db.db"
        sentinel.write_text("DO NOT TOUCH", encoding="utf-8")
        prepare_workspace(reset=True)
        assert (work / "assets" / "template.pdf").is_file()
        assert (work / "data" / "transport_demo.db").is_file()
        assert (work / "config.json").is_file()
        with closing(sqlite3.connect(work / "data" / "transport_demo.db")) as conn:
            count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert count == 2, f"Expected two fictional orders, got {count}"
        prepare_workspace(reset=False)
        with closing(sqlite3.connect(work / "data" / "transport_demo.db")) as conn:
            assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2, "Seeding duplicated records"

        db = Database(work / "config.json")
        assert len(db.list_carriers()) == 2
        assert db.search_places("loading", "Example")[0]["name"] == "Example Logistics Hub"
        assert db.get_order(1)["carrier_name"] == "Northline Demo Transport"
        db.connection.close()
        parsed = parse_driver_text(EXAMPLE_MESSAGE)
        assert parsed["full_name"] == "Jan Testowy"
        assert parsed["truck_registration"] == "DEMO101"

        docs = sorted((work / "output").rglob("*.pdf"))
        assert len(docs) == 2, f"Expected two generated PDFs, got {len(docs)}"
        with fitz.open(docs[0]) as doc:
            text = doc[0].get_text()
            assert "TRANSPORTDESK DEMO" in text
            # Windows font embeddings may extract non-breaking spaces and soft hyphens.
            normalized_text = normalize("NFKC", text).replace("\u00ad", "")
            assert "Jan Testowy" in normalized_text or "Anna Przykładowa" in normalized_text
            assert "SPECJALNE" not in text.upper()
            assert doc.page_count == 1
        assert sentinel.read_text(encoding="utf-8") == "DO NOT TOUCH"
        extra = work / "output" / "to_be_deleted_on_demo_reset.pdf"
        extra.write_text("demo junk", encoding="utf-8")
        prepare_workspace(reset=True)
        assert not extra.exists(), "Demo reset left stale demo documents"
        with closing(sqlite3.connect(work / "data" / "transport_demo.db")) as conn:
            assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
        assert sentinel.exists()
        print("OK: isolated demo, 2 orders, autocomplete, parser, PDFs, repeat seed and reset")


if __name__ == "__main__":
    main()
