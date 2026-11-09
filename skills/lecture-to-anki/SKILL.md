---
name: lecture-to-anki
description: Create and incrementally update exam-focused Anki decks from a university course folder with lecture slides, exercises, solutions, and old exams. Supports mathematics/CS question types, stable note IDs, diagrams, and .apkg packages.
---

# Lecture → Anki (v2)

Act as an evidence-grounded subject tutor, not a slide-to-bullet converter. Transform local lecture material, homework, solutions, and past exams into **accurate, exam-useful, atomic, self-contained Anki notes**. Preserve source references and maintain identities so re-imported packages **update existing notes**. Never guess an unread figure or an unsolved exam question.

## Inputs, defaults, constraints

- **Course root**: user's folder or working directory. Read it recursively, excluding `anki-output/`, `.git`, `.agents`, `build`, etc.
- **Output**: `<course>/anki-output`; canonical editable data is `cards.json`.
- **Deck**: use course folder name unless provided; **do not rename it between updates**, because that changes deck/model identity.
- **Modes**: `exam-focused` (default), `comprehensive`, `topic-specific`, and `update`.
- **Delivery**: `deck.apkg` by default, optionally `basic.txt` / `cloze.txt`. Requires `genanki` for `.apkg`. Install only with the user's permission when needed; if unavailable, export text with `--format text` and explain the limitation.
- Read and write only inside the course tree / designated output; don't change or delete lecture materials; no third-party uploads or web lookups without user request.
- Keep the same deck name, note `id` values, and card types on updates. Changing a card's note type breaks its identity and may create a separate note in Anki.

## Workflow

### 1) Determine first-run or update BEFORE extraction

If `<output>/cards.json` and `<output>/source_manifest.json` exist, first run:

```bash
python3 <skill-dir>/scripts/plan_update.py "/path/to/course"
```

Read `anki-output/update_plan.json`. It reports newly added, changed, and deleted source files (SHA-256 hashes) and existing notes supported by changed/removed files. **This step must happen before a new export**, since a successful export commits the updated manifest. If there is no baseline, generate a first full deck. An update with no material changes normally requires no new cards; still allow explicitly requested improvements.

Old v1 `cards.json` without explicit note IDs: **before editing questions**, run once:

```bash
python3 <skill-dir>/scripts/migrate_ids.py "/path/to/course/anki-output/cards.json"
```

This writes a `.bak` backup and fills missing IDs using original questions. Keep these IDs unchanged forever (even if the corresponding question's wording or cited slide changes).

### 2) Read and inventory the sources

```bash
python3 <skill-dir>/scripts/extract_sources.py "/path/to/course" \
  --output "/path/to/course/anki-output/sources.jsonl"
```

Consult `sources_report.json`; it includes per-file hashes, types, category classification, inaccessible files and empty PDF pages. Categories: lectures, homework, homework solutions, past exams, exam solutions, and notes. PDF text needs `pdftotext` or `pymupdf`. PPTX/DOCX/Markdown/LaTeX/HTML/text are supported. Image-heavy or scanned files require **visual inspection**; text extraction is not proof that all content was understood. Use local PDF/PPTX renderers as needed, not fabricated OCR/diagram interpretations. Record omitted content in `coverage.md`.

Read **all relevant source documents** on a first run. For incremental runs, primarily examine new/changed sources **and related existing material** to detect conflicts and overlapping facts. Keep an overall course syllabus/coverage map for both. Don't issue cards based only on file names or isolated snippets.

### 3) Build an exam-focused learning map

1. Slides are the **scope**: key terms, theorems, formal assumptions, notation, algorithms, examples.
2. Homework trains **transfer**: exercise strategies, proof patterns, recurring misconceptions.
3. Solutions validate answers; never invent the answer to an exam/homework problem that has no verified solution.
4. Past exams indicate frequency and expected task formats, but are not a full syllabus. Treat historical recurrence as **evidence**, never a guaranteed exam prediction.
5. Rank topics by centrality, course learning objectives, recurrence across independent materials, and exam/homework emphasis. Prioritize reusable knowledge over memorizing isolated old answers.

Before writing any cards, read both:

- [references/card-quality.md](references/card-quality.md)
- [references/math-cs-cards.md](references/math-cs-cards.md)

Use a topical coverage plan: definitions + conditions, understanding/why, application/recognition, error cases. For math/CS especially, deliberately consider **theorem / assumptions / proof strategy / proof step / counterexample / invariant / complexity / algorithm trace / reduction / micro-application**. Not every topic needs each type; choose only justified, concise, testable cards. Preserve quantifiers and prerequisites. State which complexity measure, input assumptions, and graph conventions are being used. Use Anki MathJax `\(...\)` or `\[...\]`, with correct JSON escaping.

### 4) Images and diagrams where needed

A text-only prompt can be insufficient for a graph, automaton, tree, architecture diagram, algorithm trace, geometric construction, or notation-heavy formula. If the visual is essential, include the figure in the card rather than making the learner imagine it.

**First inspect the figure visually** to determine the exact area; do not automatically copy whole slides or indiscriminately include figures.

For a cropped PDF diagram (coordinates in PDF points):

```bash
python3 <skill-dir>/scripts/prepare_media.py pdf "/path/to/course/slides/L3.pdf" \
  --page 12 --crop 100,90,490,330 --output "/path/to/course/anki-output/media"
```

For a full PPTX slide (requires LibreOffice + PyMuPDF) or an embedded PPTX picture:

```bash
python3 <skill-dir>/scripts/prepare_media.py pptx-slide "/path/to/course/slides/L3.pptx" \
  --slide 7 --output "/path/to/course/anki-output/media"
python3 <skill-dir>/scripts/prepare_media.py pptx-image "/path/to/course/slides/L3.pptx" \
  --slide 7 --image 1 --output "/path/to/course/anki-output/media"
```

For existing `.png`, `.jpg`, etc. use `prepare_media.py image ... --output ...`.

Insert exact basename into the card's HTML: `<img src="lta_example_abcdef1234.png">`. Also add `"media": ["media/lta_example_abcdef1234.png"]` to that note. **The HTML filename is basename-only** (no `media/` prefix). Assets must be local and under the chosen output folder. This ensures `.apkg` contains them. See [references/cards-schema.md](references/cards-schema.md).

Avoid storing user-specific course answers as images when copyable and screen-reader-friendly mathematical text can convey the same content; describe or caption important visual relationships in text. Figures are not a substitute for verifying conceptual correctness.

### 5) Generate/maintain cards.json

Use the schema in [references/cards-schema.md](references/cards-schema.md); every note must have a unique stable `id` (e.g. `graphs.dijkstra.nonnegative`). **NEVER derive a new ID from edited question text during an update**. Create one stable ID on first generation; persist it in `cards.json`. IDs must remain unique within the deck, and card `type` should be stable.

Include:
- `type`: `basic` or `cloze` (Anki note type; most math/CS tasks benefit from Basic).
- `kind`: e.g. `theorem`, `proof_idea`, `counterexample`, `algorithm_trace`, `complexity`, `application` (classification tag, not an Anki template).
- `front`/`back` or `text`/`extra`.
- `source_file` and `source_location`, plus `supporting_sources` when content is verified across several files.
- `tags` with `topic::...`, `priority::...`, `from::...`.
- `media` when used.

A Basic question must be independently answerable in roughly 5–30 seconds, target one fact or idea, and distinguish assumptions from conclusions. Break long algorithm walkthroughs/proofs into short testable steps. Cloze deletions should test meaningful contextual content; never cloze a whole paragraph.

### 6) Incremental update rules

On a subsequent run:

1. Read `update_plan.json`, old `cards.json`, and the new/relevant source text.
2. Revisit affected topics and notes, revise when source facts/notation have changed, **retaining note `id`**. Keep unchanged notes verbatim.
3. Add newly needed notes with *new* IDs, only if they contribute new recall/skills. Check the *entire* deck for semantic duplicates before adding.
4. Deleted sources: check alternate citations first; flag orphaned/unsupported notes for review. Never automatically erase cards or sources on a file deletion.
5. Keep `type` stable. For significant basic-to-cloze replacement, create a distinct ID, explicitly flag legacy note for manual Anki deletion (import doesn't remove missing notes).
6. Do not overwrite `cards.json` on validation errors; preserve previous version in `cards.json.bak` before large edits.
7. **Export only after every affected note is reviewed**, to commit the new `source_manifest.json`. Do not imply updating a source snapshot means its contents have been understood.

Both the package's deck/model IDs and note GUIDs are stable for the same deck and card IDs. On Anki re-import, select the option to update existing notes; Anki's import settings and modified times can affect whether changes are actually applied. **Existing scheduling generally remains when the same notes are updated**, but verify your Anki import preview. Re-import does *not* delete stale notes previously imported. Don't manually edit Anki's collection files or use AnkiConnect unless the user explicitly requests it.

### 7) Validate and export

```bash
python3 <skill-dir>/scripts/export_anki.py "/path/to/course/anki-output/cards.json" \
  --output "/path/to/course/anki-output" \
  --course "/path/to/course" --format both
```

`--format both` (default) produces `deck.apkg`, `basic.txt`, `cloze.txt` (where applicable), `export_report.json`, and `source_manifest.json`. **Import either the `.apkg` OR the `.txt` files into a particular Anki collection, not both**: different note types otherwise produce duplicates. `--format text` works without `genanki`, but its importer uses first-field matching and **cannot safely revise questions by ID**. Use `.apkg` for ongoing incremental updates. `--format apkg` skips text export.

Install `.apkg` dependency if available:

```bash
python3 -m pip install genanki
```

Check `export_report.json` for card counts, missing explicit IDs, skipped exact duplicates, media count. Resolve validation errors rather than ignoring them. Media source filenames must be unique and properly referenced. Import `.apkg` from Anki's **File → Import**.

### 8) Summarize coverage and QA

Write `<output>/coverage.md` containing:

- Materials read vs files skipped; explicitly list scan/figure gaps.
- Topics covered and number of notes by `kind` and `priority`; definition vs application balance.
- Recurring exam/homework patterns, with uncertainty and references.
- Conflicts or unresolved proof/solution assumptions.
- On update: new/changed/deleted sources, notes kept/revised/added, orphaned notes requiring review; ensure no unwarranted silent deletions.
- Exported filenames and import instructions; note that `.apkg` import doesn't delete missing notes and that Anki updates can depend on user import options.

If coverage is incomplete, say so; don't claim complete card generation for sources you couldn't inspect.
