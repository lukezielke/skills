#!/usr/bin/env python3
"""Extract page/slide-aware text from local course materials into JSONL.

This is intentionally a *text* extractor. Diagrams, figures, images, and scanned
PDF pages require independent visual inspection by Codex; their interpretation
is not silently inferred from extracted text.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

TEXT_TYPES = {".txt", ".md", ".markdown", ".tex", ".rst"}
SUPPORTED = TEXT_TYPES | {".pdf", ".pptx", ".docx", ".html", ".htm"}
VISUAL = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".gif", ".bmp", ".svg"}
KNOWN_UNSUPPORTED = {".ppt", ".doc", ".odp", ".odt", ".rtf", ".key"}
SKIP_DIRS = {
    ".git", ".agents", ".venv", "venv", "node_modules", "__pycache__",
    "anki-output", "dist", "build", ".cache",
}


def classify(path: Path) -> str:
    label = " ".join(part.lower() for part in path.parts)
    if re.search(r"(lösungen|loesungen|solutions?|musterloes|solution[-_ ]?key)", label):
        if re.search(r"(klausur|exam|altklausur|past[-_ ]?paper)", label):
            return "exam_solution"
        return "homework_solution"
    if re.search(r"(klausur|exam|altklausur|past[-_ ]?paper)", label):
        return "past_exam"
    if re.search(r"(aufgabe|übungs?|uebungs?|homework|exercise|assignment|sheet|problem[-_ ]?set)", label):
        return "homework"
    if re.search(r"(slide|lecture|vorlesung|folien|skript|session)", label):
        return "lecture"
    return "other_notes"


def xml_text(zf: zipfile.ZipFile, item: str, selector: str) -> str:
    root = ET.fromstring(zf.read(item))
    texts = []
    for n in root.iter():
        if n.tag.endswith("}" + selector) and n.text:
            texts.append(n.text)
    return " ".join(texts)


def extract_pdf(path: Path):
    if shutil.which("pdftotext"):
        p = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            capture_output=True, check=True, text=True,
        )
        pages = p.stdout.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        return [(f"p. {i}", text.strip()) for i, text in enumerate(pages, 1)]
    try:
        import fitz  # type: ignore
    except ImportError as e:
        raise RuntimeError("Install poppler-utils (pdftotext) or pymupdf to read PDF text") from e
    with fitz.open(path) as doc:
        return [(f"p. {i + 1}", page.get_text("text").strip()) for i, page in enumerate(doc)]


def extract_pptx(path: Path):
    with zipfile.ZipFile(path) as zf:
        paths = [n for n in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        paths.sort(key=lambda n: int(re.search(r"slide(\d+)", n).group(1)))
        return [(f"slide {i}", xml_text(zf, slide, "t")) for i, slide in enumerate(paths, 1)]


def extract_docx(path: Path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
        paragraphs = []
        for node in root.iter():
            if node.tag.endswith("}p"):
                bits = [x.text or "" for x in node.iter() if x.tag.endswith("}t")]
                if bits:
                    paragraphs.append("".join(bits))
        return [("document", "\n".join(paragraphs))]


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []

    def handle_data(self, data):
        self.chunks.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4"}:
            self.chunks.append("\n")


def extract(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".pptx":
        return extract_pptx(path)
    if suffix == ".docx":
        return extract_docx(path)
    if suffix in TEXT_TYPES:
        return [("document", path.read_text(encoding="utf-8-sig", errors="replace"))]
    if suffix in {".html", ".htm"}:
        parser = HTMLText()
        parser.feed(path.read_text(encoding="utf-8-sig", errors="replace"))
        return [("document", "".join(parser.chunks))]
    raise ValueError(f"Unsupported type: {suffix}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("course", type=Path, help="Course folder to scan recursively")
    ap.add_argument("--output", type=Path, help="Output JSONL (default: <course>/anki-output/sources.jsonl)")
    ns = ap.parse_args()
    root = ns.course.expanduser().resolve()
    if not root.is_dir():
        ap.error(f"Not a directory: {root}")
    out = (ns.output or root / "anki-output" / "sources.jsonl").expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    report_file = out.with_name("sources_report.json")

    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if path.resolve() in (out, report_file):
            continue
        if path.suffix.lower() in SUPPORTED | VISUAL | KNOWN_UNSUPPORTED:
            files.append(path)
    files.sort(key=lambda p: str(p.relative_to(root)).casefold())

    results = []
    segments = 0
    with out.open("w", encoding="utf-8") as fh:
        for path in files:
            rel = path.relative_to(root).as_posix()
            category = classify(path.relative_to(root))
            record = {"file": rel, "category": category, "type": path.suffix.lower(),
                      "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            if path.suffix.lower() in VISUAL:
                record.update(status="needs_visual_inspection", reason="Image content cannot be interpreted by text extraction")
                results.append(record)
                continue
            if path.suffix.lower() in KNOWN_UNSUPPORTED:
                record.update(status="unsupported", reason="Convert file to PDF or supported format")
                results.append(record)
                continue
            try:
                parsed = extract(path)
                usable = 0
                empty_locations = []
                for location, content in parsed:
                    if not content.strip():
                        empty_locations.append(location)
                        continue
                    fh.write(json.dumps({"file": rel, "category": category, "location": location,
                                         "text": content}, ensure_ascii=False) + "\n")
                    usable += 1
                    segments += 1
                record.update(status="extracted" if usable else "empty_or_scanned",
                              extracted_segments=usable, total_segments=len(parsed),
                              empty_locations=empty_locations)
            except (OSError, UnicodeError, subprocess.CalledProcessError, zipfile.BadZipFile, ET.ParseError, RuntimeError, KeyError, ValueError) as exc:
                record.update(status="error", reason=str(exc))
            results.append(record)

    counts = Counter(r["status"] for r in results)
    report = {"course": str(root), "output": str(out), "files_found": len(files),
              "segments_extracted": segments, "status_counts": dict(counts), "files": results,
              "warning": "Text extraction does not verify or capture figures, graphs, slide layouts or scanned content."}
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {segments} segments from {counts['extracted']} files; {len(files)} files found.")
    print(f"Source text: {out}\nReport: {report_file}")
    if counts["error"] or counts["unsupported"] or counts["needs_visual_inspection"] or counts["empty_or_scanned"]:
        print("Some material needs additional inspection; see the report.", file=sys.stderr)


if __name__ == "__main__":
    main()
