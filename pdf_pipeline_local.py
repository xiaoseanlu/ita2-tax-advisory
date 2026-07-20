"""
Optional local PDF → description subprocess pipeline (pdf_to_tax_situation/).

Not bundled with project-air; used as fallback when Financial Document extraction
fails or is disabled. See PDF_TO_TAX_SITUATION_DIR in .env.example.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def pdf_pipeline_dir() -> Path:
    override = (os.environ.get("PDF_TO_TAX_SITUATION_DIR") or "").strip()
    if override:
        p = Path(override).expanduser()
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        else:
            p = p.resolve()
        return p
    return (REPO_ROOT / "pdf_to_tax_situation").resolve()


def pdf_pipeline_run_script() -> Path:
    return pdf_pipeline_dir() / "run_pdf_to_description.py"


def pdf_pipeline_local_available() -> bool:
    return pdf_pipeline_run_script().is_file()


def pdf_pipeline_missing_message() -> str:
    return (
        "Local PDF pipeline is not installed (missing run_pdf_to_description.py).\n"
        f"Expected: {pdf_pipeline_run_script()}\n\n"
        "Fix one of:\n"
        "• Configure Financial Document in .env (e.g. SESSION_COOKIES + FINANCIALDOC_API_KEY, or DES IAM vars) "
        "so /api/pdf-to-description uses Intuit extraction and does not need this fallback.\n"
        "• Add the pdf_to_tax_situation folder (with run_pdf_to_description.py) under the repo root, "
        "or set PDF_TO_TAX_SITUATION_DIR to that directory."
    )
