# TransportDesk — 60–90-second live demo

Use the actual [portable Windows build](https://github.com/MichalKostepski/transport-order-generator/releases/latest). Download the Windows ZIP, extract the entire folder and run `TransportDeskDemo.exe`.

All records shown in this demo are fictional and live in a dedicated demo database.

1. **History (10s):** Open **Historia**. Show the two sample transport orders.
2. **Document editor (15s):** Select an order and choose **Wczytaj do dokumentu**. Point out that input controls follow the PDF template itself.
3. **Autocomplete (15s):** Search for `Example Logistics Hub` in the loading field, select the suggestion and show the associated address.
4. **Driver parser (15s):** Choose **Wklej dane kierowcy** and paste the following fictional text:

   ```text
   Kierowca: Jan Testowy
   Dowód: DEMO-ID-01
   Auto: DEMO101
   Naczepa: DEMO202
   Tel: 000 000 000
   ```

5. **PDF output (15s):** Select **Zapisz i utwórz PDF**, then open the generated document. Explain the separation between SQLite records and exported PDFs.
6. **Technical question (10s):** Explain why suggestions need an explicit click and why the parser allows manual corrections.

For a recording, Windows Game Bar or OBS works. Close private apps and disable notifications first. Avoid showing user accounts, real company documents or confidential filesystem paths.

Generated demo PDFs are saved under `%LOCALAPPDATA%\TransportDeskDemo\output`.

The [README gallery](../README.md#see-it-in-action) shows genuine Qt captures produced from the same fictional sample records. For a laptop presentation, work through the [manual QA checklist](../docs/MANUAL_QA.md) first.
