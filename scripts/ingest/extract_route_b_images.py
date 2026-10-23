"""Extract Route B residual images from the Vision Flow SOP PPTX, grouped by slide.

TASK-042 (Route B residual). This is a standalone extractor: it reads images
directly from the PPTX zip and writes them into per-slide folders so a human can
visually pick the wanted ones (e.g. the middle "golden image" on slides 8-14).

It does NOT use VLM. It pairs each slide's images with the slide's native text
(captions like "原始图片 / Golden Image") taken from the canonical document, so
the text evidence travels with the images.

Slide display order is resolved from ``ppt/presentation.xml`` ``<p:sldIdLst>``
(not slideN.xml filename order), matching the fix in canonical_document.py.

Outputs (gitignored ``data/processed/`` zone):
  data/processed/route_b_residual/
    images/slideNN/slideNN_cCENTER_<media>      extracted image files
    manifest.csv                                slide, seq, center, width_in, media, out_file
    slide_text/slideNN.txt                      native text per slide (UTF-8)

Usage:
  python scripts/ingest/extract_route_b_images.py
  python scripts/ingest/extract_route_b_images.py --slides 8-30,38 --pptx <path>
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PPTX = PROJECT_ROOT / "data" / "raw" / "Luster_CGLink_CGSF_Vision Flow_v1.3.pptx"
DEFAULT_OUT = PROJECT_ROOT / "data" / "processed" / "route_b_residual"
EMU_PER_INCH = 914400


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_slide_range(spec: str) -> list[int]:
    """Parse "8-30,38" into a sorted list of slide numbers."""
    result: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            result.update(range(int(lo), int(hi) + 1))
        elif part:
            result.add(int(part))
    return sorted(result)


def _ordered_slide_files(archive: zipfile.ZipFile) -> list[str]:
    """Return slide xml filenames in real display order via sldIdLst + rels."""
    pres = ET.fromstring(archive.read("ppt/presentation.xml"))
    rids: list[str] = []
    for el in pres.iter():
        if _local(el.tag) == "sldId":
            for key, val in el.attrib.items():
                if key.endswith("}id"):  # r:id, not the bare numeric id
                    rids.append(val)
    rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    rid_to_target = {e.attrib["Id"]: e.attrib["Target"].split("/")[-1] for e in rels}
    return [rid_to_target[r] for r in rids if r in rid_to_target]


def _slide_width_emu(archive: zipfile.ZipFile) -> int:
    pres = ET.fromstring(archive.read("ppt/presentation.xml"))
    for el in pres.iter():
        if _local(el.tag) == "sldSz":
            return int(el.attrib["cx"])
    return 12192000  # 13.33in default (16:9)


def _slide_height_emu(archive: zipfile.ZipFile) -> int:
    pres = ET.fromstring(archive.read("ppt/presentation.xml"))
    for el in pres.iter():
        if _local(el.tag) == "sldSz":
            return int(el.attrib["cy"])
    return 6858000  # 7.5in default (16:9)


def _pics_on_slide(archive: zipfile.ZipFile, slide_file: str) -> list[dict]:
    """Return [{media, center, width_in, x_in}] for each <p:pic> on the slide."""
    root = ET.fromstring(archive.read(f"ppt/slides/{slide_file}"))
    rels_name = f"ppt/slides/_rels/{slide_file}.rels"
    rid_to_media: dict[str, str] = {}
    if rels_name in archive.namelist():
        for e in ET.fromstring(archive.read(rels_name)):
            rid_to_media[e.attrib["Id"]] = e.attrib["Target"].split("/")[-1]

    width_emu = _slide_width_emu(archive)
    pics: list[dict] = []
    for pic in root.iter():
        if _local(pic.tag) != "pic":
            continue
        off = ext = embed = None
        for el in pic.iter():
            tag = _local(el.tag)
            if tag == "off":
                off = (int(el.attrib["x"]), int(el.attrib["y"]))
            elif tag == "ext" and "cx" in el.attrib:
                ext = (int(el.attrib["cx"]), int(el.attrib["cy"]))
            elif tag == "blip":
                for key, val in el.attrib.items():
                    if key.endswith("}embed"):
                        embed = val
        media = rid_to_media.get(embed)
        if not media:
            continue
        center = (off[0] + ext[0] / 2) / width_emu if (off and ext) else None
        pics.append({
            "media": media,
            "center": round(center, 3) if center is not None else None,
            "width_in": round(ext[0] / EMU_PER_INCH, 2) if ext else None,
            "x_in": round(off[0] / EMU_PER_INCH, 2) if off else None,
        })
    return pics


def _shapes_on_slide(archive: zipfile.ZipFile, slide_file: str) -> list[dict]:
    """Return images AND text boxes on the slide, each with center (cx, cy) in [0,1]."""
    root = ET.fromstring(archive.read(f"ppt/slides/{slide_file}"))
    rels_name = f"ppt/slides/_rels/{slide_file}.rels"
    rid_to_media: dict[str, str] = {}
    if rels_name in archive.namelist():
        for e in ET.fromstring(archive.read(rels_name)):
            rid_to_media[e.attrib["Id"]] = e.attrib["Target"].split("/")[-1]

    width_emu = _slide_width_emu(archive)
    height_emu = _slide_height_emu(archive)
    shapes: list[dict] = []
    for shape in root.iter():
        kind = _local(shape.tag)
        if kind not in ("pic", "sp"):
            continue
        off = ext = media = None
        runs: list[str] = []
        for el in shape.iter():
            tag = _local(el.tag)
            if tag == "off":
                off = (int(el.attrib["x"]), int(el.attrib["y"]))
            elif tag == "ext" and "cx" in el.attrib:
                ext = (int(el.attrib["cx"]), int(el.attrib["cy"]))
            elif tag == "blip":
                for key, val in el.attrib.items():
                    if key.endswith("}embed"):
                        media = rid_to_media.get(val)
            elif tag == "t" and el.text:
                runs.append(el.text)
        if not (off and ext):
            continue
        shapes.append({
            "kind": kind,
            "cx": (off[0] + ext[0] / 2) / width_emu,
            "cy": (off[1] + ext[1] / 2) / height_emu,
            "media": media,
            "text": " ".join(runs).strip(),
        })
    return shapes


def _native_text_by_slide(canonical_path: Path | None) -> dict[int, str]:
    if not canonical_path or not canonical_path.exists():
        return {}
    doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    out: dict[int, str] = {}
    for block in doc.get("blocks", []):
        if block.get("block_type") != "text":
            continue
        slide = block.get("source_anchor", {}).get("slide")
        if slide is not None:
            out[slide] = block.get("text", "")
    return out


def _text_from_shapes(archive: zipfile.ZipFile, slide_file: str) -> str:
    """Extract all text from sp shapes on a slide, joined by newlines."""
    shapes = _shapes_on_slide(archive, slide_file)
    lines = [s["text"] for s in shapes if s["kind"] == "sp" and s["text"]]
    return "\n".join(lines)


def _filter_steps_and_requirement(raw: str) -> str:
    """Keep only lines that belong to 'Steps of Auto Calibration' or 'Requirement' blocks.

    Drops slide titles, diagram labels, and other fragments that aren't
    procedural evidence (e.g. 'Pos1', 'Module', '12 Poses').
    """
    kept: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("Steps of") or s.startswith("Requirement"):
            kept.append(s)
    return "\n".join(kept)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Route B residual images grouped by slide.")
    parser.add_argument("--pptx", default=str(DEFAULT_PPTX))
    parser.add_argument("--canonical", default=None, help="canonical JSON for native captions (auto-detect if omitted)")
    parser.add_argument("--slides", default="8-30,38", help='per-slide image+text dump range (golden slides auto-excluded)')
    parser.add_argument("--golden", default="8-14", help='slides to extract as middle-column VLM bundles (img+text)')
    parser.add_argument("--golden-band", default="0.42,0.58", help='cx band [lo,hi] for golden column pic shapes')
    parser.add_argument("--golden-txt-band", default="0.35,0.60", help='cx band [lo,hi] for golden column sp (text label) shapes — wider to catch labels left-aligned beside images')
    parser.add_argument("--golden-extra-pics", default="", help='extra pic media to force-include in golden bundles, format "slide:media,slide:media" e.g. "13:image30.png"')
    parser.add_argument("--text-slides", default="", help='text-only slides (no images extracted), filtered to Steps/Requirement blocks, e.g. "31-35"')
    parser.add_argument("--img-text-slides", default="", help='image slides that also need full native text written, e.g. "38"')
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pptx_path = Path(args.pptx)
    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX not found: {pptx_path}")

    canonical_path = Path(args.canonical) if args.canonical else None
    if canonical_path is None:
        hits = sorted((PROJECT_ROOT / "data" / "processed" / "unstructured").glob("*Vision_Flow*_canonical.json"))
        canonical_path = hits[0] if hits else None

    # Exclude golden slides from the full image dump — they only go through the bundle path.
    golden_set = set(_parse_slide_range(args.golden)) if args.golden else set()
    wanted = [s for s in _parse_slide_range(args.slides) if s not in golden_set]
    text_only = _parse_slide_range(args.text_slides) if args.text_slides else []
    img_text = set(_parse_slide_range(args.img_text_slides)) if args.img_text_slides else set()

    out_root = Path(args.out)
    img_root = out_root / "images"
    text_root = out_root / "slide_text"

    with zipfile.ZipFile(pptx_path) as archive:
        slide_files = _ordered_slide_files(archive)
        native_text = _native_text_by_slide(canonical_path)

        rows: list[dict] = []
        for slide_no in wanted:
            if slide_no > len(slide_files):
                continue
            slide_file = slide_files[slide_no - 1]
            pics = _pics_on_slide(archive, slide_file)
            for seq, pic in enumerate(pics):
                stem = f"slide{slide_no:02d}_c{pic['center']}_{pic['media']}"
                out_file = img_root / f"slide{slide_no:02d}" / stem
                rows.append({
                    "slide": slide_no,
                    "seq": seq,
                    "center": pic["center"],
                    "width_in": pic["width_in"],
                    "media": pic["media"],
                    "out_file": str(out_file.relative_to(PROJECT_ROOT)),
                })
                if not args.dry_run:
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_bytes(archive.read(f"ppt/media/{pic['media']}"))

            if slide_no in img_text:
                slide_txt = _text_from_shapes(archive, slide_file)
                if not args.dry_run and slide_txt:
                    text_root.mkdir(parents=True, exist_ok=True)
                    (text_root / f"slide{slide_no:02d}.txt").write_text(slide_txt, encoding="utf-8")

        # Text-only slides: extract Steps/Requirement blocks from PPTX shapes, no images.
        text_only_summary: list[tuple[int, int]] = []
        for slide_no in text_only:
            if slide_no > len(slide_files):
                continue
            slide_file = slide_files[slide_no - 1]
            raw = _text_from_shapes(archive, slide_file)
            txt = _filter_steps_and_requirement(raw)
            char_count = len(txt)
            text_only_summary.append((slide_no, char_count))
            if not args.dry_run and txt:
                text_root.mkdir(parents=True, exist_ok=True)
                (text_root / f"slide{slide_no:02d}.txt").write_text(txt, encoding="utf-8")

        # Golden-column VLM bundles: middle-column images + their text labels,
        # ordered top-to-bottom, bundled per slide for N's VLM run.
        # pic and sp use separate cx bands: text labels are often left-aligned
        # beside their image and fall slightly outside the image band.
        lo, hi = (float(x) for x in args.golden_band.split(","))
        tlo, thi = (float(x) for x in args.golden_txt_band.split(","))

        # Parse per-slide extra pic whitelist: "13:image30.png,14:image99.png" -> {13: {"image30.png"}, ...}
        extra_pics: dict[int, set[str]] = {}
        if args.golden_extra_pics:
            for item in args.golden_extra_pics.split(","):
                slide_str, media = item.strip().split(":", 1)
                extra_pics.setdefault(int(slide_str), set()).add(media.strip())

        bundle_root = out_root / "vlm_bundles"
        bundle_summary: list[tuple[int, int, int]] = []
        for slide_no in _parse_slide_range(args.golden):
            if slide_no > len(slide_files):
                continue
            all_shapes = _shapes_on_slide(archive, slide_files[slide_no - 1])
            slide_extras = extra_pics.get(slide_no, set())
            shapes = [
                s for s in all_shapes
                if (s["kind"] == "pic" and s["media"] and (lo <= s["cx"] <= hi or s["media"] in slide_extras))
                or (s["kind"] == "sp" and tlo <= s["cx"] <= thi)
            ]
            shapes.sort(key=lambda s: s["cy"])
            lines: list[str] = []
            seen_media: set[str] = set()
            n_img = n_txt = 0
            for s in shapes:
                if s["kind"] == "pic" and s["media"]:
                    if s["media"] in seen_media:  # dedupe repeated blip refs
                        continue
                    seen_media.add(s["media"])
                    lines.append(f"[IMG] {s['media']}")
                    n_img += 1
                    if not args.dry_run:
                        dst = bundle_root / f"slide{slide_no:02d}" / s["media"]
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(archive.read(f"ppt/media/{s['media']}"))
                elif s["kind"] == "sp" and s["text"]:
                    lines.append(f"[TXT] {s['text']}")
                    n_txt += 1
            bundle_summary.append((slide_no, n_img, n_txt))
            if not args.dry_run and lines:
                bdir = bundle_root / f"slide{slide_no:02d}"
                bdir.mkdir(parents=True, exist_ok=True)
                (bdir / "bundle.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

        if not args.dry_run:
            out_root.mkdir(parents=True, exist_ok=True)
            with (out_root / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=["slide", "seq", "center", "width_in", "media", "out_file"])
                writer.writeheader()
                writer.writerows(rows)

    # Summary
    by_slide: dict[int, int] = {}
    for r in rows:
        by_slide[r["slide"]] = by_slide.get(r["slide"], 0) + 1
    total_imgs = len(rows)
    prefix = "DRY-RUN: " if args.dry_run else ""
    excluded = sorted(golden_set & set(_parse_slide_range(args.slides)))
    print(f"{prefix}slides={args.slides} (golden excluded: {excluded})  images={total_imgs}  pptx={pptx_path.name}")
    for slide_no in sorted(by_slide):
        print(f"  slide {slide_no:>2}: {by_slide[slide_no]} 图")
    print(f"\n--- golden 列 VLM bundles (slides {args.golden}, pic cx∈[{args.golden_band}], txt cx∈[{args.golden_txt_band}], extra={args.golden_extra_pics}) ---")
    for slide_no, n_img, n_txt in bundle_summary:
        print(f"  slide {slide_no:>2}: {n_img} 图 + {n_txt} 文字标签")
    if text_only_summary:
        print(f"\n--- text-only slides ({args.text_slides}) ---")
        for slide_no, char_count in text_only_summary:
            print(f"  slide {slide_no:>2}: {char_count} chars")
    if not args.dry_run:
        print(f"\nimages -> {img_root}")
        print(f"native text -> {text_root}")
        print(f"vlm bundles -> {out_root / 'vlm_bundles'}")
        print(f"manifest -> {out_root / 'manifest.csv'}")


if __name__ == "__main__":
    main()
