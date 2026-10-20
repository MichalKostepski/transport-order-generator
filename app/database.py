from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class DatabaseError(RuntimeError):
    pass


class Database:
    """Small database layer supporting local SQLite and optional SQL Server."""

    def __init__(self, config_path: Path):
        self.base_dir = config_path.resolve().parent
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        self.settings = config["database"]
        self.engine = self.settings.get("engine", "sqlite").lower()
        self._database_location = ""
        self.connection = self._connect()
        self._initialize_schema()
        self._backfill_places_from_order_history()
        self._repair_legacy_place_rows()

    def _connect(self):
        if self.engine == "sqlite":
            db_path = (self.base_dir / self.settings["sqlite_path"]).resolve()
            self._database_location = str(db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection

        if self.engine == "sqlserver":
            self._database_location = "SQL Server"
            try:
                import pyodbc  # type: ignore
            except ImportError as exc:
                raise DatabaseError(
                    "Brakuje pakietu pyodbc. Uruchom INSTALUJ.bat albo polecenie: pip install pyodbc"
                ) from exc
            try:
                return pyodbc.connect(self.settings["sqlserver_connection_string"])
            except Exception as exc:
                raise DatabaseError(f"Nie udało się połączyć z SQL Server: {exc}") from exc

        raise DatabaseError(f"Nieobsługiwany silnik bazy: {self.engine}")

    def _backfill_places_from_order_history(self) -> None:
        """Move legacy places from order history into the editable dictionary.

        Older application versions sometimes kept an address only inside an order.
        From v3.5 suggestions use the places table exclusively, so edits made in the
        Baza danych tab are immediately authoritative.
        """
        try:
            pairs = (
                ("loading", "load_place_name", "load_address"),
                ("client", "unload_place_name", "unload_address"),
            )
            for kind, name_column, address_column in pairs:
                rows = self.fetch_all(
                    f"SELECT {name_column} AS name, {address_column} AS address, "
                    "MAX(updated_at) AS last_used FROM orders "
                    f"WHERE {name_column} IS NOT NULL "
                    f"AND LTRIM(RTRIM(CAST({name_column} AS TEXT))) <> '' "
                    f"GROUP BY {name_column}, {address_column}"
                    if self.is_sqlite
                    else
                    f"SELECT CONVERT(NVARCHAR(1000), {name_column}) AS name, "
                    f"CONVERT(NVARCHAR(2000), {address_column}) AS address, "
                    "MAX(updated_at) AS last_used FROM orders "
                    f"WHERE {name_column} IS NOT NULL "
                    f"AND LTRIM(RTRIM(CONVERT(NVARCHAR(1000), {name_column}))) <> '' "
                    f"GROUP BY CONVERT(NVARCHAR(1000), {name_column}), "
                    f"CONVERT(NVARCHAR(2000), {address_column})"
                )
                for row in rows:
                    name = str(row.get("name", "") or "").strip()
                    address = str(row.get("address", "") or "").strip()
                    if name and not self.get_place(kind, name, address):
                        self.execute(
                            "INSERT INTO places(kind, name, address, updated_at) VALUES (?, ?, ?, ?)",
                            (kind, name, address, str(row.get("last_used", "") or self._now())),
                        )
        except Exception as exc:
            raise DatabaseError(f"Nie udało się przenieść wcześniejszych adresów do słownika: {exc}") from exc

    @staticmethod
    def _split_legacy_place(name: Any, address: Any) -> tuple[str, str]:
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

    def _repair_legacy_place_rows(self) -> None:
        """Split old unloading suggestions that accidentally stored address in name."""
        rows = self.fetch_all("SELECT id, kind, name, address FROM places")
        for row in rows:
            old_name = str(row.get("name", "") or "")
            old_address = str(row.get("address", "") or "")
            name, address = self._split_legacy_place(old_name, old_address)
            if not name or (name == old_name.strip() and address == old_address.strip()):
                continue
            existing = self.get_place(str(row.get("kind", "")), name, address)
            if existing and int(existing.get("id", 0)) != int(row.get("id", 0)):
                self.execute("DELETE FROM places WHERE id = ?", (row.get("id"),))
            else:
                self.execute(
                    "UPDATE places SET name = ?, address = ?, updated_at = ? WHERE id = ?",
                    (name, address, self._now(), row.get("id")),
                )

    @property
    def is_sqlite(self) -> bool:
        return self.engine == "sqlite"

    @property
    def database_location(self) -> str:
        return self._database_location or self.engine

    def _initialize_schema(self) -> None:
        statements = self._sqlite_schema() if self.is_sqlite else self._sqlserver_schema()
        cursor = self.connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
            self.connection.commit()
            self._apply_migrations()
        except Exception as exc:
            self.connection.rollback()
            raise DatabaseError(f"Nie udało się utworzyć tabel: {exc}") from exc
        finally:
            cursor.close()

    def _apply_migrations(self) -> None:
        """Update databases created by earlier versions without deleting user data."""
        cursor = self.connection.cursor()
        try:
            if self.is_sqlite:
                cursor.execute("PRAGMA table_info(orders)")
                columns = {str(row[1]).lower() for row in cursor.fetchall()}
                if "internal_notes" not in columns:
                    cursor.execute("ALTER TABLE orders ADD COLUMN internal_notes TEXT NOT NULL DEFAULT ''")

                # Earlier versions allowed only one address per company name. Rebuild the
                # table so the same name can have several distinct address variants.
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='places'")
                row = cursor.fetchone()
                create_sql = str(row[0] or "") if row else ""
                compact_sql = "".join(create_sql.lower().split())
                if "unique(kind,name,address)" not in compact_sql:
                    cursor.execute("ALTER TABLE places RENAME TO places_legacy")
                    cursor.execute(
                        """
                        CREATE TABLE places (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            kind TEXT NOT NULL,
                            name TEXT NOT NULL,
                            address TEXT NOT NULL DEFAULT '',
                            updated_at TEXT NOT NULL,
                            UNIQUE(kind, name, address)
                        )
                        """
                    )
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO places(id, kind, name, address, updated_at)
                        SELECT id, kind, name, COALESCE(address, ''), updated_at
                        FROM places_legacy
                        """
                    )
                    cursor.execute("DROP TABLE places_legacy")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_places_kind_name ON places(kind, name)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_places_kind_name_address ON places(kind, name, address)")
            else:
                cursor.execute(
                    "IF COL_LENGTH('dbo.orders', 'internal_notes') IS NULL "
                    "ALTER TABLE dbo.orders ADD internal_notes NVARCHAR(MAX) NOT NULL "
                    "CONSTRAINT DF_orders_internal_notes DEFAULT ''"
                )
                cursor.execute(
                    "IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='orders' "
                    "AND COLUMN_NAME='load_date' AND DATA_TYPE='date') "
                    "ALTER TABLE dbo.orders ALTER COLUMN load_date NVARCHAR(100) NULL"
                )
                cursor.execute(
                    "IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='orders' "
                    "AND COLUMN_NAME='unload_date' AND DATA_TYPE='date') "
                    "ALTER TABLE dbo.orders ALTER COLUMN unload_date NVARCHAR(100) NULL"
                )
                cursor.execute(
                    "IF EXISTS (SELECT 1 FROM sys.key_constraints "
                    "WHERE [type] = 'UQ' AND [name] = 'UQ_places_kind_name') "
                    "ALTER TABLE dbo.places DROP CONSTRAINT UQ_places_kind_name"
                )
            self.connection.commit()
        except Exception as exc:
            self.connection.rollback()
            raise DatabaseError(f"Nie udało się zaktualizować struktury bazy: {exc}") from exc
        finally:
            cursor.close()

    @staticmethod
    def _sqlite_schema() -> List[str]:
        return [
            """
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(kind, name, address)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS carriers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                address TEXT NOT NULL DEFAULT '',
                nip TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier_id INTEGER,
                full_name TEXT NOT NULL,
                id_card TEXT NOT NULL DEFAULT '',
                pesel TEXT NOT NULL DEFAULT '',
                truck_registration TEXT NOT NULL DEFAULT '',
                trailer_registration TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(carrier_id) REFERENCES carriers(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_ordinal INTEGER NOT NULL,
                order_month INTEGER NOT NULL,
                order_year INTEGER NOT NULL,
                order_number TEXT NOT NULL UNIQUE,
                order_date TEXT NOT NULL,
                internal_notes TEXT NOT NULL DEFAULT '',
                carrier_name TEXT NOT NULL DEFAULT '',
                carrier_details TEXT NOT NULL DEFAULT '',
                load_place_name TEXT NOT NULL DEFAULT '',
                load_address TEXT NOT NULL DEFAULT '',
                load_date TEXT NOT NULL DEFAULT '',
                unload_place_name TEXT NOT NULL DEFAULT '',
                unload_address TEXT NOT NULL DEFAULT '',
                unload_date TEXT NOT NULL DEFAULT '',
                service_value TEXT NOT NULL DEFAULT '',
                payment TEXT NOT NULL DEFAULT '',
                cargo_type TEXT NOT NULL DEFAULT '',
                cargo_tons REAL NOT NULL DEFAULT 0,
                driver_full_name TEXT NOT NULL DEFAULT '',
                driver_id_card TEXT NOT NULL DEFAULT '',
                driver_pesel TEXT NOT NULL DEFAULT '',
                truck_registration TEXT NOT NULL DEFAULT '',
                trailer_registration TEXT NOT NULL DEFAULT '',
                driver_phone TEXT NOT NULL DEFAULT '',
                pdf_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_places_kind_name ON places(kind, name)",
            "CREATE INDEX IF NOT EXISTS idx_places_kind_name_address ON places(kind, name, address)",
            "CREATE INDEX IF NOT EXISTS idx_drivers_name ON drivers(full_name)",
            "CREATE INDEX IF NOT EXISTS idx_orders_period ON orders(order_year, order_month, order_ordinal)",
        ]

    @staticmethod
    def _sqlserver_schema() -> List[str]:
        return [
            """
            IF OBJECT_ID('dbo.places', 'U') IS NULL
            CREATE TABLE dbo.places (
                id INT IDENTITY(1,1) PRIMARY KEY,
                kind NVARCHAR(30) NOT NULL,
                name NVARCHAR(250) NOT NULL,
                address NVARCHAR(1000) NOT NULL DEFAULT '',
                updated_at DATETIME2 NOT NULL,
                CONSTRAINT UQ_places_kind_name_address UNIQUE(kind, name, address)
            )
            """,
            """
            IF OBJECT_ID('dbo.carriers', 'U') IS NULL
            CREATE TABLE dbo.carriers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(250) NOT NULL UNIQUE,
                address NVARCHAR(MAX) NOT NULL DEFAULT '',
                nip NVARCHAR(30) NOT NULL DEFAULT '',
                email NVARCHAR(250) NOT NULL DEFAULT '',
                phone NVARCHAR(80) NOT NULL DEFAULT '',
                updated_at DATETIME2 NOT NULL
            )
            """,
            """
            IF OBJECT_ID('dbo.drivers', 'U') IS NULL
            CREATE TABLE dbo.drivers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                carrier_id INT NULL,
                full_name NVARCHAR(250) NOT NULL,
                id_card NVARCHAR(80) NOT NULL DEFAULT '',
                pesel NVARCHAR(20) NOT NULL DEFAULT '',
                truck_registration NVARCHAR(30) NOT NULL DEFAULT '',
                trailer_registration NVARCHAR(30) NOT NULL DEFAULT '',
                phone NVARCHAR(80) NOT NULL DEFAULT '',
                updated_at DATETIME2 NOT NULL,
                CONSTRAINT FK_drivers_carriers FOREIGN KEY(carrier_id) REFERENCES dbo.carriers(id) ON DELETE SET NULL
            )
            """,
            """
            IF OBJECT_ID('dbo.orders', 'U') IS NULL
            CREATE TABLE dbo.orders (
                id INT IDENTITY(1,1) PRIMARY KEY,
                order_ordinal INT NOT NULL,
                order_month INT NOT NULL,
                order_year INT NOT NULL,
                order_number NVARCHAR(50) NOT NULL UNIQUE,
                order_date DATE NOT NULL,
                internal_notes NVARCHAR(MAX) NOT NULL DEFAULT '',
                carrier_name NVARCHAR(250) NOT NULL DEFAULT '',
                carrier_details NVARCHAR(MAX) NOT NULL DEFAULT '',
                load_place_name NVARCHAR(250) NOT NULL DEFAULT '',
                load_address NVARCHAR(MAX) NOT NULL DEFAULT '',
                load_date NVARCHAR(100) NULL,
                unload_place_name NVARCHAR(250) NOT NULL DEFAULT '',
                unload_address NVARCHAR(MAX) NOT NULL DEFAULT '',
                unload_date NVARCHAR(100) NULL,
                service_value NVARCHAR(80) NOT NULL DEFAULT '',
                payment NVARCHAR(250) NOT NULL DEFAULT '',
                cargo_type NVARCHAR(250) NOT NULL DEFAULT '',
                cargo_tons DECIMAL(12,3) NOT NULL DEFAULT 0,
                driver_full_name NVARCHAR(250) NOT NULL DEFAULT '',
                driver_id_card NVARCHAR(80) NOT NULL DEFAULT '',
                driver_pesel NVARCHAR(20) NOT NULL DEFAULT '',
                truck_registration NVARCHAR(30) NOT NULL DEFAULT '',
                trailer_registration NVARCHAR(30) NOT NULL DEFAULT '',
                driver_phone NVARCHAR(80) NOT NULL DEFAULT '',
                pdf_path NVARCHAR(1000) NOT NULL DEFAULT '',
                created_at DATETIME2 NOT NULL,
                updated_at DATETIME2 NOT NULL
            )
            """,
        ]

    def _rows(self, cursor) -> List[Dict[str, Any]]:
        if self.is_sqlite:
            return [dict(row) for row in cursor.fetchall()]
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            return self._rows(cursor)
        finally:
            cursor.close()

    def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def list_places(self, kind: str) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT id, kind, name, address, updated_at FROM places WHERE kind = ? ORDER BY updated_at DESC, name",
            (kind,),
        )

    def search_places(self, kind: str, query: str = "", limit: int = 12) -> List[Dict[str, Any]]:
        """Search the editable place dictionary used by live autocomplete."""
        kind = str(kind or "").strip().lower()
        if kind not in {"loading", "client"}:
            return []

        rows = self.list_places(kind)

        def normal(value: Any) -> str:
            return " ".join(str(value or "").strip().casefold().split())

        needle = normal(query)
        unique: List[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            name, address = self._split_legacy_place(row.get("name", ""), row.get("address", ""))
            key = (normal(name), normal(address))
            if not name or key in seen:
                continue
            seen.add(key)
            unique.append({"id": row.get("id"), "name": name, "address": address})

        if not needle:
            return unique[: max(1, int(limit))]

        def score(row: Dict[str, Any]) -> tuple[int, str, str]:
            name = normal(row.get("name", ""))
            address = normal(row.get("address", ""))
            if name == needle:
                rank = 0
            elif name.startswith(needle):
                rank = 1
            elif any(word.startswith(needle) for word in name.split()):
                rank = 2
            elif needle in name:
                rank = 3
            elif needle in address:
                rank = 4
            else:
                rank = 99
            return rank, name, address

        matches = [row for row in unique if score(row)[0] < 99]
        matches.sort(key=score)
        return matches[: max(1, int(limit))]

    def get_place(self, kind: str, name: str, address: Optional[str] = None) -> Optional[Dict[str, Any]]:
        name = name.strip()
        if address is not None:
            return self.fetch_one(
                """
                SELECT id, kind, name, address FROM places
                WHERE kind = ? AND LOWER(name) = LOWER(?) AND LOWER(address) = LOWER(?)
                ORDER BY updated_at DESC
                """,
                (kind, name, address.strip()),
            )
        return self.fetch_one(
            """
            SELECT id, kind, name, address FROM places
            WHERE kind = ? AND LOWER(name) = LOWER(?)
            ORDER BY updated_at DESC
            """,
            (kind, name),
        )

    def save_place(self, kind: str, name: str, address: str) -> Optional[int]:
        name = name.strip()
        address = address.strip()
        if not name:
            return None
        # Exact name + exact address is one record. A changed address creates a new record.
        existing = self.get_place(kind, name, address)
        now = self._now()
        if existing:
            self.execute("UPDATE places SET updated_at = ? WHERE id = ?", (now, existing["id"]))
            return int(existing["id"])
        self.execute(
            "INSERT INTO places(kind, name, address, updated_at) VALUES (?, ?, ?, ?)",
            (kind, name, address, now),
        )
        saved = self.get_place(kind, name, address)
        return int(saved["id"]) if saved else None

    def list_carriers(self) -> List[Dict[str, Any]]:
        return self.fetch_all("SELECT * FROM carriers ORDER BY updated_at DESC, name")

    def get_carrier(self, name: str) -> Optional[Dict[str, Any]]:
        return self.fetch_one("SELECT * FROM carriers WHERE LOWER(name) = LOWER(?)", (name.strip(),))

    def save_carrier(self, name: str, details: str = "") -> Optional[int]:
        """Save only the carrier name; legacy detail columns remain for compatibility."""
        name = name.strip()
        if not name:
            return None
        existing = self.get_carrier(name)
        now = self._now()
        if existing:
            self.execute("UPDATE carriers SET updated_at = ? WHERE id = ?", (now, existing["id"]))
            return int(existing["id"])
        self.execute(
            "INSERT INTO carriers(name, address, nip, email, phone, updated_at) VALUES (?, '', '', '', '', ?)",
            (name, now),
        )
        saved = self.get_carrier(name)
        return int(saved["id"]) if saved else None

    def list_drivers(self, carrier_name: str = "") -> List[Dict[str, Any]]:
        if carrier_name.strip():
            return self.fetch_all(
                """
                SELECT d.*, c.name AS carrier_name
                FROM drivers d LEFT JOIN carriers c ON c.id = d.carrier_id
                WHERE LOWER(c.name) = LOWER(?)
                ORDER BY d.updated_at DESC, d.full_name
                """,
                (carrier_name.strip(),),
            )
        return self.fetch_all(
            """
            SELECT d.*, c.name AS carrier_name
            FROM drivers d LEFT JOIN carriers c ON c.id = d.carrier_id
            ORDER BY d.updated_at DESC, d.full_name
            """
        )

    def get_driver(self, full_name: str, carrier_name: str = "") -> Optional[Dict[str, Any]]:
        if carrier_name.strip():
            return self.fetch_one(
                """
                SELECT d.*, c.name AS carrier_name
                FROM drivers d LEFT JOIN carriers c ON c.id = d.carrier_id
                WHERE LOWER(d.full_name) = LOWER(?) AND LOWER(c.name) = LOWER(?)
                ORDER BY d.updated_at DESC
                """,
                (full_name.strip(), carrier_name.strip()),
            )
        return self.fetch_one(
            """
            SELECT d.*, c.name AS carrier_name
            FROM drivers d LEFT JOIN carriers c ON c.id = d.carrier_id
            WHERE LOWER(d.full_name) = LOWER(?)
            ORDER BY d.updated_at DESC
            """,
            (full_name.strip(),),
        )

    def save_driver(self, data: Dict[str, Any], carrier_id: Optional[int]) -> Optional[int]:
        full_name = str(data.get("full_name", "")).strip()
        if not full_name:
            return None
        carrier_name = str(data.get("carrier_name", "")).strip()
        # Business assumption: two drivers do not share the same full name.
        existing = self.get_driver(full_name)
        now = self._now()
        values = (
            carrier_id,
            full_name,
            str(data.get("id_card", "")).strip(),
            str(data.get("pesel", "")).strip(),
            str(data.get("truck_registration", "")).strip(),
            str(data.get("trailer_registration", "")).strip(),
            str(data.get("phone", "")).strip(),
            now,
        )
        if existing:
            self.execute(
                """
                UPDATE drivers SET carrier_id = ?, full_name = ?, id_card = ?, pesel = ?,
                    truck_registration = ?, trailer_registration = ?, phone = ?, updated_at = ?
                WHERE id = ?
                """,
                values + (existing["id"],),
            )
            return int(existing["id"])
        self.execute(
            """
            INSERT INTO drivers(carrier_id, full_name, id_card, pesel, truck_registration,
                trailer_registration, phone, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        saved = self.get_driver(full_name)
        return int(saved["id"]) if saved else None

    def next_order_ordinal(self, month: int, year: int) -> int:
        row = self.fetch_one(
            "SELECT MAX(order_ordinal) AS max_number FROM orders WHERE order_month = ? AND order_year = ?",
            (month, year),
        )
        return int(row["max_number"] or 0) + 1 if row else 1

    def save_order(self, data: Dict[str, Any]) -> int:
        now = self._now()
        existing = self.fetch_one("SELECT id, created_at FROM orders WHERE order_number = ?", (data["order_number"],))
        columns = [
            "order_ordinal", "order_month", "order_year", "order_number", "order_date",
            "internal_notes", "carrier_name", "carrier_details", "load_place_name", "load_address", "load_date",
            "unload_place_name", "unload_address", "unload_date", "service_value", "payment",
            "cargo_type", "cargo_tons", "driver_full_name", "driver_id_card", "driver_pesel",
            "truck_registration", "trailer_registration", "driver_phone", "pdf_path",
        ]
        values = [data.get(column, "") for column in columns]
        if existing:
            assignments = ", ".join(f"{column} = ?" for column in columns)
            self.execute(
                f"UPDATE orders SET {assignments}, updated_at = ? WHERE id = ?",
                values + [now, existing["id"]],
            )
            return int(existing["id"])

        placeholders = ", ".join("?" for _ in columns)
        self.execute(
            f"INSERT INTO orders({', '.join(columns)}, created_at, updated_at) VALUES ({placeholders}, ?, ?)",
            values + [now, now],
        )
        saved = self.fetch_one("SELECT id FROM orders WHERE order_number = ?", (data["order_number"],))
        if not saved:
            raise DatabaseError("Zapisano zamówienie, ale nie udało się odczytać jego identyfikatora.")
        return int(saved["id"])


    def update_order_pdf_path(self, order_id: int, pdf_path: str) -> None:
        self.execute(
            "UPDATE orders SET pdf_path = ?, updated_at = ? WHERE id = ?",
            (str(pdf_path or ""), self._now(), int(order_id)),
        )

    def distinct_order_values(self, column: str, limit: int = 250) -> List[str]:
        """Return recently used non-empty values for safe, whitelisted order fields."""
        allowed = {
            "carrier_name", "carrier_details", "load_place_name", "load_address", "load_date",
            "unload_place_name", "unload_address", "unload_date", "service_value", "payment",
            "cargo_type", "cargo_tons", "driver_full_name", "driver_id_card", "driver_pesel",
            "truck_registration", "trailer_registration", "driver_phone",
        }
        if column not in allowed:
            raise DatabaseError(f"Pole nie jest dostępne do podpowiedzi: {column}")
        limit = max(1, min(int(limit), 1000))
        if self.is_sqlite:
            rows = self.fetch_all(
                f"SELECT {column} AS value, MAX(updated_at) AS last_used "
                f"FROM orders WHERE {column} IS NOT NULL AND TRIM(CAST({column} AS TEXT)) <> '' "
                f"GROUP BY {column} ORDER BY last_used DESC LIMIT ?",
                (limit,),
            )
        else:
            expression = f"CONVERT(NVARCHAR(4000), {column})"
            rows = self.fetch_all(
                f"SELECT TOP {limit} {expression} AS value, MAX(updated_at) AS last_used "
                f"FROM orders WHERE {column} IS NOT NULL "
                f"AND LTRIM(RTRIM({expression})) <> '' "
                f"GROUP BY {expression} ORDER BY last_used DESC"
            )
        values: List[str] = []
        for row in rows:
            value = row.get("value", "")
            if value is None:
                continue
            if column == "cargo_tons":
                try:
                    number = float(value)
                    text = str(int(number)) if number.is_integer() else str(number).replace(".", ",")
                except (TypeError, ValueError):
                    text = str(value)
            else:
                text = str(value)
            if text.strip():
                values.append(text.strip())
        return values

    def list_orders(self, limit: int = 300) -> List[Dict[str, Any]]:
        if self.is_sqlite:
            return self.fetch_all(
                "SELECT * FROM orders ORDER BY order_year DESC, order_month DESC, order_ordinal DESC LIMIT ?",
                (limit,),
            )
        return self.fetch_all(
            f"SELECT TOP {int(limit)} * FROM orders ORDER BY order_year DESC, order_month DESC, order_ordinal DESC"
        )

    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        return self.fetch_one("SELECT * FROM orders WHERE id = ?", (order_id,))

    def delete_order(self, order_id: int) -> None:
        """Permanently remove one complete order from history."""
        self.execute("DELETE FROM orders WHERE id = ?", (int(order_id),))

    def get_dictionary_row(self, category: str, row_id: int) -> Optional[Dict[str, Any]]:
        category = str(category or "")
        row_id = int(row_id)
        if category in {"loading", "client"}:
            return self.fetch_one(
                "SELECT id, kind, name, address, updated_at FROM places WHERE id = ? AND kind = ?",
                (row_id, category),
            )
        if category == "carrier":
            return self.fetch_one(
                "SELECT id, name, updated_at FROM carriers WHERE id = ?",
                (row_id,),
            )
        if category == "driver":
            return self.fetch_one(
                """
                SELECT d.*, c.name AS carrier_name
                FROM drivers d LEFT JOIN carriers c ON c.id = d.carrier_id
                WHERE d.id = ?
                """,
                (row_id,),
            )
        raise DatabaseError("Nieznana kategoria słownika.")

    def update_dictionary_row(self, category: str, row_id: int, data: Dict[str, Any]) -> None:
        """Update one visible dictionary record directly from the application."""
        category = str(category or "")
        row_id = int(row_id)
        now = self._now()
        try:
            if category in {"loading", "client"}:
                name = str(data.get("name", "") or "").strip()
                address = str(data.get("address", "") or "").strip()
                if not name:
                    raise DatabaseError("Nazwa miejsca nie może być pusta.")
                duplicate = self.get_place(category, name, address)
                if duplicate and int(duplicate["id"]) != row_id:
                    raise DatabaseError("Taki sam wpis z identycznym adresem już istnieje w bazie.")
                self.execute(
                    "UPDATE places SET name = ?, address = ?, updated_at = ? WHERE id = ? AND kind = ?",
                    (name, address, now, row_id, category),
                )
                return

            if category == "carrier":
                name = str(data.get("name", "") or "").strip()
                if not name:
                    raise DatabaseError("Nazwa przewoźnika nie może być pusta.")
                duplicate = self.get_carrier(name)
                if duplicate and int(duplicate["id"]) != row_id:
                    raise DatabaseError("Przewoźnik o tej nazwie już istnieje w bazie.")
                self.execute(
                    "UPDATE carriers SET name = ?, updated_at = ? WHERE id = ?",
                    (name, now, row_id),
                )
                return

            if category == "driver":
                full_name = str(data.get("full_name", "") or "").strip()
                if not full_name:
                    raise DatabaseError("Imię i nazwisko kierowcy nie może być puste.")
                duplicate = self.get_driver(full_name)
                if duplicate and int(duplicate["id"]) != row_id:
                    raise DatabaseError("Kierowca o tym imieniu i nazwisku już istnieje w bazie.")
                carrier_name = str(data.get("carrier_name", "") or "").strip()
                carrier_id = self.save_carrier(carrier_name) if carrier_name else None
                self.execute(
                    """
                    UPDATE drivers SET carrier_id = ?, full_name = ?, id_card = ?, pesel = ?,
                        truck_registration = ?, trailer_registration = ?, phone = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        carrier_id, full_name,
                        str(data.get("id_card", "") or "").strip(),
                        str(data.get("pesel", "") or "").strip(),
                        str(data.get("truck_registration", "") or "").strip().upper(),
                        str(data.get("trailer_registration", "") or "").strip().upper(),
                        str(data.get("phone", "") or "").strip(),
                        now, row_id,
                    ),
                )
                return

            raise DatabaseError("Nieznana kategoria słownika.")
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(f"Nie udało się zapisać zmian w bazie: {exc}") from exc

    def delete_dictionary_row(self, category: str, row_id: int) -> None:
        table = {"loading": "places", "client": "places", "carrier": "carriers", "driver": "drivers"}.get(category)
        if not table:
            raise DatabaseError("Nieznana kategoria słownika.")
        if table == "places":
            self.execute("DELETE FROM places WHERE id = ? AND kind = ?", (row_id, category))
        else:
            self.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
