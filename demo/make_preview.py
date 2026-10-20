"""Render the REAL generated example PDF as an image (no fake GUI screenshot)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from demo.workspace import prepare_workspace


def main() -> None:
    import fitz
    work = prepare_workspace()
    source = work / "output" / "2026" / "10" / "1_10_UT_2026.pdf"
    target = PROJECT_ROOT / "docs" / "screenshots" / "sample-transport-order.png"
    if not source.exists():
        from demo.sample_data import example_orders
        sys.path.insert(0, str(PROJECT_ROOT / "app"))
        from pdf_generator import PdfGenerator
        PdfGenerator(work / "config.json").generate(example_orders()[0])
    doc = fitz.open(source)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        pix.save(target)
    finally:
        doc.close()
    print("Generated PDF preview:", target)


if __name__ == "__main__":
    main()
