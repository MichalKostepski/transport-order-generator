# TransportDesk — Resume notes

**TransportDesk | Python, PySide6, SQLite, PyMuPDF, PyInstaller, GitHub Actions**

Developed a Windows desktop application used by a fertilizer distribution company to create and print transport orders. Implemented a PDF-based editor, database-backed autocomplete for carriers and locations, a regex-based driver-message parser, and an order history with document regeneration.

## Suggested CV bullets

- Developed a **desktop tool used in daily business operations** to prepare and print transport documents using Python, PySide6 and PyMuPDF.
- Built **SQLite-backed autocomplete and editable dictionaries** for carriers, drivers and loading/unloading locations.
- Added **structured data extraction from pasted driver messages** using regular expressions, plus order history and PDF regeneration.
- Automated **portable Windows EXE packaging and CI smoke tests** with PyInstaller and GitHub Actions; published downloadable demo builds through GitHub Releases.

## Demo for interviews

Download the latest portable Windows demo from [GitHub Releases](https://github.com/MichalKostepski/transport-order-generator/releases/latest). It runs without a Python installation and uses only fictional sample data.

- Start the isolated demo and open an existing order.
- Show the autocomplete selection and automatic address fill.
- Paste a fictional driver message and explain the parser's limitations.
- Generate the document and point out the SQLite/PDF separation.

No unmeasured performance gains or deployment numbers are asserted. Verify that the description matches your own contribution and your right to show this work.
