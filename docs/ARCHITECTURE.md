# Architecture

TransportDesk is a Windows desktop application with a Qt user interface, a persistence layer and a document generator. All components are implemented in Python.

```text
run.py / demo.run_demo
        |
        v
app/main.py  (PySide6 interface)
   |        |       |
   v        v       v
Database  Parser  PdfGenerator
 SQLite    regex    PyMuPDF
```

## PDF-aligned editor

`PdfFormCanvas` renders the selected document template with PyMuPDF, then places editable Qt widgets over it. Each widget is mapped to a PDF coordinate rectangle. Zooming scales both the rendered page and the overlay geometry. The generated PDF is filled independently using the coordinate map in `pdf_generator.py`.

This makes editing feel close to filling the document itself; changing the underlying PDF template requires reviewing the field coordinates.

## Search and autocomplete

`PlaceEditor` searches previously saved location names and addresses. The ranking used by `search_places()` prioritizes exact matches, prefixes and then substring matches; records are deduplicated. The popup requires an explicit choice and does not silently select the first result while the user is typing.

Carrier and driver dictionaries are editable within the application. Other previously used values can be suggested by `SmartCombo` widgets.

## Text parsing

`parse_driver_text()` recognizes Polish labels for the driver's name, identity details, vehicle registrations and contact number. Regular expressions also handle some unlabeled formats. Unusual message formats may need a manual correction. No external recognition service is involved.

## Persistence and document lifecycle

The default database is SQLite, containing order records and reusable dictionaries. Saving updates a matching order number or creates a new record. PDF files are stored separately under year/month directories, with their locations referenced in the order history. The application can regenerate a PDF from stored order data when necessary.

The data layer also has an optional SQL Server connection path. This is not asserted as a verified production deployment in this source release.

## Separate demo workspace

The `demo` package configures `%LOCALAPPDATA%/TransportDeskDemo` on Windows (or a separate user-local folder on Linux). It seeds two fictional orders and creates PDF examples. The `TRANSPORT_APP_ROOT` environment variable points only the **demo process** to this workspace, leaving the normal application configuration alone. `DEMO_RESET.bat` removes only its own SQLite demo database and reseeds the examples.

## Tests and limitations

`demo/test_demo.py` verifies seeded records, nonduplicating initialization, database lookups, parser output, generated PDFs and isolated reset behavior. Additional targeted tests are under `narzedzia/`. GitHub Actions runs source-level tests on Windows and Ubuntu, then separately smoke-tests the packaged Windows EXE (Qt GUI startup, sample order and PDF availability). The Linux Xvfb runner captures readable screenshots of the genuine Qt editor and history from fictional data. Real printer output and UI layouts on individual laptop displays still require manual checks. The demonstration template is neutral and has intentionally different branding from the company's operational document.
