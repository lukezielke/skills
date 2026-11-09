# Lecture → Anki (Codex skill, v2)

Generate and incrementally update exam-focused flashcards from a local course folder containing lectures, assignments, solutions, old exams, PDFs, PowerPoint files and notes. Includes mathematical/CS question patterns, source references, visual cards and ready-to-import `.apkg` files.

## Install

Copy this **entire directory** into `~/.agents/skills/lecture-to-anki/` (globally) or `<course>/.agents/skills/lecture-to-anki/` (per project):

```bash
mkdir -p ~/.agents/skills
cp -r lecture-to-anki ~/.agents/skills/
```

For recommended `.apkg` output:

```bash
python3 -m pip install genanki
```

On Ubuntu, PDF text extraction via Poppler and figures via PyMuPDF:

```bash
sudo apt install poppler-utils
python3 -m pip install pymupdf
```

You can use a virtualenv for Python packages. Full-slide PPTX rendering needs LibreOffice (`sudo apt install libreoffice`); embedded picture extraction works without LibreOffice. Nonstandard image conversion optionally needs Pillow.

## Generate from a course folder

```bash
cd ~/University/Algorithms
codex
```

Prompt inside Codex:

```text
$lecture-to-anki Build a high-quality, exam-focused Anki deck from this course folder.
Include definitions, theorems, assumptions, proof ideas, counterexamples,
algorithm reasoning, complexity, and small application questions where appropriate.
Ground every answer in the slides, homework solutions, or past exams.
Use diagrams when necessary. Keep permanent note IDs, export deck.apkg,
and report gaps in the source material.
```

Expected output:

```text
anki-output/
  sources.jsonl
  sources_report.json
  cards.json               # canonical dataset; keep this for updates
  media/                   # only if visuals are used
  deck.apkg                # recommended import format
  basic.txt                # optional text fallback
  cloze.txt                # optional text fallback
  export_report.json
  source_manifest.json     # snapshot of successful source review/export
  coverage.md
```

Open Anki → **File → Import** → `deck.apkg`. Do **not** also import `basic.txt` and `cloze.txt` in the same collection, or you'll get duplicates because note types differ.

## When a new lecture or exam is added

Run Codex in the same course folder:

```text
$lecture-to-anki Update my existing deck with the new or changed course material.
Preserve all existing note IDs, inspect update_plan.json, and add or revise
only cards affected by new facts. Do not delete unsupported cards silently.
Export a revised deck.apkg and summarize changes.
```

Internally, the skill runs the `plan_update.py` command before regenerating cards to compare current course files against the previous `source_manifest.json` using SHA-256 hashes; its `update_plan.json` lists changed sources and linked notes. On a successful full export, `source_manifest.json` is updated. Re-import the `.apkg`, selecting Anki's update option as appropriate. **Anki does not delete notes that have disappeared from the package.** Changes made inside Anki can affect whether the imported version overwrites the existing note; review the import preview.

For older decks generated with v1, migrate missing IDs **before editing the question text**:

```bash
python3 ~/.agents/skills/lecture-to-anki/scripts/migrate_ids.py anki-output/cards.json
```

A `.bak` copy is created. The first v2 `.apkg` import is not guaranteed to merge with v1's default Basic/Cloze text notes because v2 uses purpose-built note types; if switching, check for duplicate notes in Anki. From the first v2 `.apkg` import onward, stable IDs are used for subsequent updates.

## Manual tooling

```bash
# Find new, changed, removed sources and affected notes (do this FIRST on updates)
python3 ~/.agents/skills/lecture-to-anki/scripts/plan_update.py .

# Extract text and locate image-dependent content
python3 ~/.agents/skills/lecture-to-anki/scripts/extract_sources.py .

# Prepare a PDF figure (coordinates in PDF points)
python3 ~/.agents/skills/lecture-to-anki/scripts/prepare_media.py pdf Lectures/L3.pdf \
  --page 7 --crop 90,80,460,310 --output anki-output/media

# Export .apkg and text files; commit the source snapshot
python3 ~/.agents/skills/lecture-to-anki/scripts/export_anki.py anki-output/cards.json \
  --course . --format both

# Without genanki: tab-separated text only (cannot reliably update modified questions)
python3 ~/.agents/skills/lecture-to-anki/scripts/export_anki.py anki-output/cards.json \
  --course . --format text
```

### Limitations

- The extraction script retrieves **text**, not the meaning of a graph or screenshot. Codex must inspect those visually and mark unreviewed material in `coverage.md`.
- Auto-prioritization from old exams does not predict exam probabilities.
- `.apkg` updates maintain stable IDs *within the same named deck and unchanged note type*; changing deck name/type or switching formats may create duplicates.
- Source removal is a review event, not an automatic request to delete flashcards already in Anki.
- Text imports may need Anki's media folder configured manually; `.apkg` is recommended for images.

## Run automated tests

```bash
python3 -m unittest discover -s tests -v
```

The tests cover source diffing, explicit ID preservation, media preparation and validation, and text fallback. The optional package integration check runs when `genanki` is installed.
