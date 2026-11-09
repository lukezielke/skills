# cards.json schema (v2)

`cards.json` is canonical and editable. Output package import uses **stable note IDs**; never change an `id` on an incremental update. Export creates `kind::<kind>` tag automatically if absent.

```json
{
  "deck": "Algorithms",
  "cards": [
    {
      "id": "graphs.bfs.queue_invariant",
      "type": "basic",
      "kind": "invariant",
      "front": "When BFS visits vertices in an unweighted graph, what invariant governs the order of distances in its queue?",
      "back": "Queue distances are in nondecreasing order from the source.",
      "source_file": "Lectures/L05.pdf",
      "source_location": "p. 16",
      "supporting_sources": [{"file": "Exercises/Sheet03.pdf", "location": "p. 2"}],
      "tags": ["topic::graph_search", "priority::high", "from::lecture", "from::homework"]
    },
    {
      "id": "graphs.bfs.time_complexity",
      "type": "cloze",
      "kind": "complexity",
      "text": "With adjacency lists, BFS uses {{c1::\\(O(n+m)\\)}} time for n vertices and m edges.",
      "extra": "Each vertex and edge is inspected O(1) times.",
      "source_file": "Lectures/L05.pdf",
      "source_location": "p. 18",
      "tags": ["topic::graph_search", "priority::high", "from::lecture"]
    }
  ]
}
```

## Fields

| Field | Required | Description |
| --- | --- | --- |
| `deck` | top level | Persistent deck name, do not rename between updates. |
| `cards` | top level | Array of note objects. |
| `id` | every new note | Stable unique identifier, `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`. Required in new AI-generated cards; legacy notes can be migrated. |
| `type` | yes | `basic` or `cloze`. Keep unchanged for updates. |
| `kind` | recommended | CS/math pedagogical category, e.g. `theorem`, `counterexample`, `algorithm_trace`, `application` or `concept`. |
| `front`,`back` | Basic | Self-contained question and concise HTML-compatible answer. |
| `text` | Cloze | Anki text with at least one `{{c1::...}}` marker. |
| `extra` | Cloze | Optional answer-side explanation. |
| `source_file` | yes | Relative path to a source file. |
| `source_location` | yes | `p. 12`, `slide 8` or section pointer. |
| `supporting_sources` | optional | Array of `{ "file": "...", "location": "..." }` for additional citations; tracked for updates. |
| `tags` | yes | JSON list of whitespace-free strings, e.g. `topic::sorting`, `from::exam`, `priority::high`. |
| `media` | optional | Paths relative to `anki-output/`, usually `media/lta_filename.png`. Media must exist. |

**Embedding media**: `front`, `back`, `text` or `extra` may contain `<img src="lta_filename.png">`. This is **just the basename**, not `media/lta_filename.png`. Add `"media": ["media/lta_filename.png"]` to the note. The script checks that referenced media exists and includes it inside `deck.apkg`. Only safe local image/audio file types are supported. Use unique filenames (the `prepare_media.py` tool makes names content-specific).

**JSON escaping**: Use `"\\(n^2\\)"` for `\(n^2\)` rendered by MathJax. Use `<br>` rather than literal newlines inside displayed content; ensure literal HTML characters in mathematical prose are encoded, e.g. `&lt;` for `<`.

**Legacy fallback**: the exporter can derive an ID when none is present, but this fallback depends on original wording. Run `scripts/migrate_ids.py cards.json` once to add permanent IDs *before editing any existing questions*.

## Export artifacts

`python3 scripts/export_anki.py anki-output/cards.json --course COURSE --format both`

- `deck.apkg`: preferred for ongoing updates and embedded media. Uses private per-course Basic/Cloze models, and deterministic model/deck IDs and note GUIDs. Requires `genanki`.
- `basic.txt`, `cloze.txt`: text-import fallback; uses standard Anki Basic/Cloze fields; **not ID-safe when questions change**.
- `export_report.json`: counts, warnings, asset details.
- `source_manifest.json`: hash snapshot of source documents, written **only after successful export** when `--course` was specified; `plan_update.py` compares against it later.

Do **not** import both formats into the same Anki collection: they contain distinct Anki note types. The `.apkg` update mechanism cannot automatically remove previously imported notes that are no longer present in `cards.json`. Updating also depends on your Anki import settings and local edits.
