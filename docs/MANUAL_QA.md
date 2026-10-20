# TransportDesk — Manual Windows Demo QA

GitHub Actions tests the source code and the packaged EXE automatically, but a real laptop presentation still needs the following checks. This list is meant for the actual machine you will use during an interview.

## Preparation

- [ ] Sign in to GitHub and download the ZIP from the [latest private Release](https://github.com/MichalKostepski/transport-order-generator/releases/latest).
- [ ] Extract the full `TransportDeskDemo` directory. Keep `_internal` next to `TransportDeskDemo.exe`.
- [ ] Launch the EXE on Windows 10/11 x64 without installing Python or Docker.
- [ ] If Windows SmartScreen reports an unknown publisher, inspect the source and release provenance; never disable security protections just to run a demo.

## Main workflow

- [ ] Verify the **Historia** tab shows exactly two fictional orders on a fresh demo workspace.
- [ ] Open each order in the PDF-aligned editor; make sure number/date controls and button labels are readable at your laptop resolution.
- [ ] Test loading and destination autocomplete and verify the address fills only after selecting a suggestion.
- [ ] Paste the fictional driver message from [the recording guide](../demo/RECORDING_GUIDE.md) and verify the parsed fields; manually correct a field.
- [ ] Generate a PDF and open it. Inspect the full page for overlaps, missing text and any company-specific branding.
- [ ] If printing matters, test the **Print** button with Microsoft Print to PDF or an authorized test printer.
- [ ] Quit and reopen the app to confirm the demo history persists.

## Isolation & presentation

- [ ] Confirm the app only creates its local sample workspace under `%LOCALAPPDATA%\TransportDeskDemo` and does not open company documents.
- [ ] Close other applications and hide personal notifications before any screen recording.
- [ ] Make sure the demo screenshot gallery and sample PDF in the README match the current app layout.
- [ ] Get permission before sharing any employer-related source code publicly. The GitHub repository should remain private until that review is complete.

If any check fails, do not present it as a finished production feature. Note the problem and reproduce it using fictional data.
