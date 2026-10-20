# TransportDesk demo

The portable Windows build runs the **real TransportDesk application** using fictional data, a separate SQLite database and a neutral PDF template. No production documents or company database are included.

## Download the Windows EXE

1. Sign in to GitHub and open the [latest TransportDesk Demo release](https://github.com/MichalKostepski/transport-order-generator/releases/latest).
2. In **Assets**, download **TransportDeskDemo-Windows-x64.zip**.
3. Extract the ZIP completely. Open the **TransportDeskDemo** folder and double-click **TransportDeskDemo.exe**.

The executable is portable: **Python, pip and Docker are not required**. Keep the bundled **_internal** folder alongside the EXE. This build targets Windows x64. Windows may show a warning for an unsigned application; only run software you trust.

On first launch the app creates its demo data under:

- Database: `%LOCALAPPDATA%\TransportDeskDemo\data\transport_demo.db`
- Generated documents: `%LOCALAPPDATA%\TransportDeskDemo\output`

The **Historia** tab contains two fictional transport orders. Opening the previous orders, looking up locations, pasting example driver details and generating PDFs all use local demo data.

To reset the demo completely, close the app and delete only the **TransportDeskDemo** folder under **%LOCALAPPDATA%**. Do not remove any other folder or company database.

## Build pipeline

The [Windows build workflow](../.github/workflows/windows-portable-demo.yml) runs on GitHub Actions. It installs dependencies, checks the source-code demo, creates a **PyInstaller onedir** executable and launches the packaged program using an offscreen Qt test. The test verifies GUI startup, order history and sample PDFs. Only if the tests pass does the workflow upload a ZIP and publish a GitHub Release.

Windows builds appear in [Releases](https://github.com/MichalKostepski/transport-order-generator/releases). CI tests do not verify an actual printer or every possible screen resolution; those require a manual check on a laptop.

## Work on the source code instead

If you want to edit the application, you can download the source repository and run **DEMO_START.bat**. That developer-friendly route installs Python dependencies on first launch. The Windows Release ZIP is better for interviews and demonstrations.

## Actual application screenshots

The [main README gallery](../README.md#see-it-in-action) contains real PySide6 views of the PDF editor and order history captured with two fictional orders. A Linux Xvfb runner provides a readable UI screenshot; Windows CI independently tests the packaged EXE.

## Screenshots and a demo recording

The repository contains an example generated PDF at [docs/sample-transport-order.pdf](../docs/sample-transport-order.pdf). A source checkout on Windows can capture the Qt editor and history with:

~~~powershell
.\.venv\Scripts\python.exe demo\capture_screenshots.py
~~~

The captures should be reviewed to ensure they contain only fictional data before sharing. See the [recording guide](RECORDING_GUIDE.md). Before a live interview, follow the [Windows demo QA checklist](../docs/MANUAL_QA.md).
