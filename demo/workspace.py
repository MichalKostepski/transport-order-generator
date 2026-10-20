"""Create a self-contained demonstration; never read the production config."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def demo_home() -> Path:
    override = os.environ.get("TRANSPORT_DEMO_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    else:
        base = Path.home() / ".local" / "share"
    return base / "TransportDeskDemo"


def prepare_workspace(reset: bool = False, seed_pdf: bool = True) -> Path:
    from demo.sample_data import example_orders
    work = demo_home()
    work.mkdir(parents=True, exist_ok=True)
    db_file = work / "data" / "transport_demo.db"
    config_file = work / "config.json"
    source_template = PROJECT_ROOT / "assets" / "template.pdf"
    template = work / "assets" / "template.pdf"
    if not source_template.is_file():
        raise FileNotFoundError(f"Demo PDF template missing: {source_template}")
    template.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_template, template)

    if reset:
        if db_file.exists():
            db_file.unlink()
        demo_output = work / "output"
        if demo_output.is_dir() and not demo_output.is_symlink():
            shutil.rmtree(demo_output)

    config = {
        "database": {"engine": "sqlite", "sqlite_path": "data/transport_demo.db", "sqlserver_connection_string": ""},
        "pdf": {"template_path": str(template), "output_directory": "output", "demo_mode": True},
    }
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    first_run = not db_file.exists()
    sys.path.insert(0, str(PROJECT_ROOT / "app"))
    from database import Database
    from pdf_generator import PdfGenerator

    db = Database(config_file)
    try:
        gen = PdfGenerator(config_file)
        if first_run:
            for record in example_orders():
                carrier_id = db.save_carrier(record["carrier_name"])
                db.save_place("loading", record["load_place_name"], record["load_address"])
                db.save_place("client", record["unload_place_name"], record["unload_address"])
                db.save_driver({
                    "full_name": record["driver_full_name"],
                    "carrier_name": record["carrier_name"],
                    "id_card": record["driver_id_card"],
                    "pesel": record["driver_pesel"],
                    "truck_registration": record["truck_registration"],
                    "trailer_registration": record["trailer_registration"],
                    "phone": record["driver_phone"],
                }, carrier_id)
                if seed_pdf:
                    record["pdf_path"] = str(gen.generate(record))
                db.save_order(record)
    finally:
        db.connection.close()
    return work


if __name__ == "__main__":
    result = prepare_workspace(reset="--reset" in set(sys.argv[1:]))
    print("Demo workspace:", result)
    print("Database:", result / "data" / "transport_demo.db")
    print("Documents:", result / "output")
