from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from services.ingestion.cad_2d_pipeline_v2.artifacts import sha256_file

try:
    import pymupdf
except ModuleNotFoundError:  # pragma: no cover - exercised by deployment checks
    pymupdf = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover - exercised by deployment checks
    PdfReader = None  # type: ignore[assignment,misc]


MASK_RECTS: tuple[tuple[float, float, float, float], ...] = (
    (714.33, 732.44, 1011.97, 782.96),
    (1011.97, 732.44, 1190.55, 782.96),
)


def require_dependencies() -> None:
    if pymupdf is None or PdfReader is None:
        raise RuntimeError(
            "PyMuPDF and pypdf are required; install requirements/base.txt"
        )


def _overlaps(
    observed: tuple[float, float, float, float],
    expected: tuple[float, float, float, float],
) -> bool:
    return not (
        observed[2] <= expected[0]
        or observed[0] >= expected[2]
        or observed[3] <= expected[1]
        or observed[1] >= expected[3]
    )


def _words_in_rectangles(page: Any, rectangles: Iterable[tuple[float, float, float, float]]) -> int:
    words = page.get_text("words") or []
    return sum(
        1
        for word in words
        if any(
            _overlaps(tuple(float(value) for value in word[:4]), rectangle)
            for rectangle in rectangles
        )
    )


def _black_ratio(page: Any, rectangle: tuple[float, float, float, float]) -> float:
    clip = pymupdf.Rect(rectangle) + (1, 1, -1, -1)
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(1, 1),
        colorspace=pymupdf.csRGB,
        alpha=False,
        clip=clip,
    )
    samples = pixmap.samples
    pixels = max(1, pixmap.width * pixmap.height)
    dark = sum(
        samples[offset] <= 10
        and samples[offset + 1] <= 10
        and samples[offset + 2] <= 10
        for offset in range(0, len(samples), 3)
    )
    return dark / pixels


def _annotation_count(page: Any) -> int:
    annotations = page.annots()
    return 0 if annotations is None else sum(1 for _ in annotations)


def _widget_count(page: Any) -> int:
    widgets = page.widgets()
    return 0 if widgets is None else sum(1 for _ in widgets)


def _metadata_value_count(metadata: dict[str, Any] | None) -> int:
    ignored = {"format", "encryption"}
    return sum(
        bool(str(value).strip())
        for key, value in (metadata or {}).items()
        if key not in ignored and value is not None
    )


def verify_redacted_pdf(
    path: Path,
    *,
    rectangles: tuple[tuple[float, float, float, float], ...] = MASK_RECTS,
    minimum_black_ratio: float = 0.98,
) -> dict[str, Any]:
    require_dependencies()
    with pymupdf.open(path) as document:
        page_records = []
        for page in document:
            page_records.append(
                {
                    "page_number": page.number + 1,
                    "words_intersecting_redactions": _words_in_rectangles(page, rectangles),
                    "minimum_redaction_black_ratio": min(
                        _black_ratio(page, rectangle) for rectangle in rectangles
                    ),
                    "annotation_count": _annotation_count(page),
                    "widget_count": _widget_count(page),
                }
            )
        embedded_file_count = document.embfile_count()
        optional_content_group_count = len(document.get_ocgs())
        xml_metadata_present = bool(document.xref_xml_metadata())
        metadata_value_count = _metadata_value_count(document.metadata)

    reader = PdfReader(str(path))
    root = reader.trailer["/Root"]
    names = root.get("/Names")
    javascript_present = bool(
        isinstance(names, dict) and names.get("/JavaScript") is not None
    ) or root.get("/OpenAction") is not None
    acroform_present = root.get("/AcroForm") is not None

    result = {
        "page_count": len(page_records),
        "page_records": page_records,
        "words_intersecting_redactions": sum(
            row["words_intersecting_redactions"] for row in page_records
        ),
        "minimum_redaction_black_ratio": min(
            row["minimum_redaction_black_ratio"] for row in page_records
        ),
        "annotation_count": sum(row["annotation_count"] for row in page_records),
        "widget_count": sum(row["widget_count"] for row in page_records),
        "embedded_file_count": embedded_file_count,
        "optional_content_group_count": optional_content_group_count,
        "xml_metadata_present": xml_metadata_present,
        "metadata_value_count": metadata_value_count,
        "javascript_present": javascript_present,
        "acroform_present": acroform_present,
    }
    result["passed"] = (
        result["words_intersecting_redactions"] == 0
        and result["minimum_redaction_black_ratio"] >= minimum_black_ratio
        and result["annotation_count"] == 0
        and result["widget_count"] == 0
        and result["embedded_file_count"] == 0
        and result["optional_content_group_count"] == 0
        and not result["xml_metadata_present"]
        and result["metadata_value_count"] == 0
        and not result["javascript_present"]
        and not result["acroform_present"]
    )
    return result


def redact_pdf(
    source: Path,
    destination: Path,
    *,
    rectangles: tuple[tuple[float, float, float, float], ...] = MASK_RECTS,
) -> dict[str, Any]:
    require_dependencies()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(source) as document:
        before_words = 0
        for page in document:
            for rectangle in rectangles:
                if not page.rect.contains(pymupdf.Rect(rectangle)):
                    raise ValueError(
                        f"redaction rectangle falls outside page {page.number + 1}"
                    )
            before_words += _words_in_rectangles(page, rectangles)
            for rectangle in rectangles:
                page.add_redact_annot(
                    pymupdf.Rect(rectangle), fill=(0, 0, 0), cross_out=False
                )
            if not page.apply_redactions():
                raise RuntimeError(f"no redaction was applied on page {page.number + 1}")

        document.scrub(
            attached_files=True,
            clean_pages=True,
            embedded_files=True,
            hidden_text=True,
            javascript=True,
            metadata=True,
            redactions=True,
            redact_images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
            remove_links=True,
            reset_fields=True,
            reset_responses=True,
            thumbnails=True,
            xml_metadata=True,
        )
        document.save(
            destination,
            garbage=4,
            clean=True,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            incremental=False,
            encryption=pymupdf.PDF_ENCRYPT_NONE,
            preserve_metadata=False,
            use_objstms=1,
        )

    verification = verify_redacted_pdf(destination, rectangles=rectangles)
    if not verification["passed"]:
        raise ValueError("written PDF failed destructive-redaction verification")
    return {
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(destination),
        "source_bytes": source.stat().st_size,
        "output_bytes": destination.stat().st_size,
        "words_intersecting_before": before_words,
        "verification": verification,
    }


