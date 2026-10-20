from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from database import Database
from pdf_generator import PdfGenerator


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        config = {
            "database": {
                "engine": "sqlite",
                "sqlite_path": "data/test.db",
                "sqlserver_connection_string": "",
            },
            "pdf": {
                "template_path": str(ROOT / "assets" / "template.pdf"),
                "output_directory": "PDF",
            },
        }
        config_path = work / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        database = Database(config_path)
        carrier_id = database.save_carrier("Przewoznik testowy")
        database.save_driver(
            {
                "full_name": "Jan Testowy",
                "carrier_name": "Przewoznik testowy",
                "id_card": "ABC 123456",
                "pesel": "00000000000",
                "truck_registration": "RTA 12345",
                "trailer_registration": "RTA 54321",
                "phone": "500 600 700",
            },
            carrier_id,
        )
        driver = database.get_driver("Jan Testowy")
        assert driver and driver["truck_registration"] == "RTA 12345"

        order = {
            "order_ordinal": 1,
            "order_month": 8,
            "order_year": 2026,
            "order_number": "1/08/UT/2026",
            "order_date": "2026-08-04",
            "internal_notes": "",
            "carrier_name": "Przewoznik testowy",
            "carrier_details": "",
            "load_place_name": "Firma A",
            "load_address": "ul. Testowa 1",
            "load_date": "04.08.2026 / 05.08.2026",
            "unload_place_name": "Klient B",
            "unload_address": "ul. Odbiorcza 2",
            "unload_date": "05.08.2026",
            "service_value": "1 250 zl netto",
            "payment": "30 dni przelew",
            "cargo_type": "Nawoz",
            "cargo_tons": 24,
            "driver_full_name": "Jan Testowy",
            "driver_id_card": "ABC 123456",
            "driver_pesel": "00000000000",
            "truck_registration": "RTA 12345",
            "trailer_registration": "RTA 54321",
            "driver_phone": "500 600 700",
            "pdf_path": "",
        }
        order_id = database.save_order(order)

        # Test edytowalnego slownika i podpowiedzi miejsc.
        loading_id = database.save_place("loading", order["load_place_name"], order["load_address"])
        assert database.search_places("loading", "Fir")[0]["name"] == "Firma A"
        database.update_dictionary_row(
            "loading", int(loading_id), {"name": "Firma A po korekcie", "address": "ul. Nowa 9"}
        )
        assert database.search_places("loading", "korek")[0]["address"] == "ul. Nowa 9"

        driver_row = database.get_driver("Jan Testowy")
        database.update_dictionary_row(
            "driver", int(driver_row["id"]),
            {
                "full_name": "Jan Testowy", "carrier_name": "Przewoznik testowy",
                "id_card": "XYZ 999999", "pesel": "00000000000",
                "truck_registration": "RTA 99999", "trailer_registration": "RTA 88888",
                "phone": "111 222 333",
            },
        )
        assert database.get_driver("Jan Testowy")["id_card"] == "XYZ 999999"

        generator = PdfGenerator(config_path)
        pdf_path = generator.generate(order)
        database.update_order_pdf_path(order_id, str(pdf_path))
        assert pdf_path.exists()
        assert database.get_order(order_id)["pdf_path"] == str(pdf_path)

        database.connection.close()

    print("Test aplikacji zakonczony pomyslnie.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
