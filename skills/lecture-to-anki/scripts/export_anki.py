#!/usr/bin/env python3
"""Validate cards.json; export stable-ID Anki .apkg (genanki) and/or TSV.

Requires `python3 -m pip install genanki` for .apkg export. Text-only export
uses the standard library. cards.json remains the canonical editing format.
"""

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

CLOZE = re.compile(r'\{\{c([1-9]\d*)::(.+?)(?:::[^{}]*?)?\}\}', re.DOTALL)
IMAGE = re.compile(r'<img\s+[^>]*src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
SOUND = re.compile(r'\[sound:([^\]]+)\]')
VALID_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')
EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.mp3', '.ogg', '.wav'}


def compact(s):
    return ' '.join(s.split()).casefold()


def field(value):
    return value.replace('\t', ' ').replace('\r\n', '<br>').replace('\r', '<br>').replace('\n', '<br>')


def stable_number(*parts):
    payload = '\u241f'.join(parts).encode('utf-8')
    # In genanki's recommended 10-digit ID range; deterministic across runs.
    return 1_000_000_000 + int.from_bytes(hashlib.sha256(payload).digest()[:8], 'big') % 1_000_000_000


def legacy_id(typ, note):
    # Deterministic fallback for old decks; editing question will change identity.
    first = note.get('front') if typ == 'basic' else note.get('text')
    payload = json.dumps([typ, note.get('source_file', ''), compact(first or '')], ensure_ascii=False)
    return 'legacy-' + hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]


def require_str(note, key, idx, errors, required=True):
    value = note.get(key, '')
    if not isinstance(value, str) or (required and not value.strip()):
        errors.append(f'Card {idx}: {key!r} must be a {"nonempty " if required else ""}string')
        return ''
    return value.strip()


def normalize_and_validate(src: Path, media_root: Path):
    data = json.loads(src.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or not isinstance(data.get('deck'), str) or not data['deck'].strip():
        raise ValueError("Top level requires a nonempty 'deck' string")
    deck = data['deck'].strip()
    if '\n' in deck or '\r' in deck:
        raise ValueError('Deck name cannot contain newlines')
    cards = data.get('cards')
    if not isinstance(cards, list):
        raise ValueError("Top level 'cards' must be an array")
    errors = []
    used_ids = set()
    seen_first = {}
    duplicates = 0
    legacy = 0
    normalized = []
    media_paths = {}
    media_root = media_root.resolve()
    for idx, note in enumerate(cards, 1):
        if not isinstance(note, dict):
            errors.append(f'Card {idx}: must be an object')
            continue
        typ = require_str(note, 'type', idx, errors).lower()
        if typ not in {'basic', 'cloze'}:
            errors.append(f'Card {idx}: invalid type {typ!r}')
            continue
        sf = require_str(note, 'source_file', idx, errors)
        sl = require_str(note, 'source_location', idx, errors)
        if sf and (Path(sf).is_absolute() or '..' in Path(sf).parts):
            errors.append(f'Card {idx}: source_file must be relative within course: {sf}')
        tags = note.get('tags')
        if not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() and not re.search(r'\s', t) for t in tags):
            errors.append(f'Card {idx}: tags must be a list of nonempty whitespace-free strings')
            tags = []
        tags = list(dict.fromkeys(t.strip() for t in tags))
        if typ == 'basic':
            front = require_str(note, 'front', idx, errors)
            back = require_str(note, 'back', idx, errors)
        else:
            front = require_str(note, 'text', idx, errors)
            back = require_str(note, 'extra', idx, errors, required=False)
            matches = CLOZE.findall(front)
            if not matches or any(not answer.strip() for number, answer in matches):
                errors.append(f'Card {idx}: Cloze needs valid nonempty {{{{c1::...}}}} deletion(s)')
        card_id = note.get('id')
        if card_id is None:
            card_id = legacy_id(typ, note)
            legacy += 1
        if not isinstance(card_id, str) or not VALID_ID.fullmatch(card_id):
            errors.append(f'Card {idx}: id must match {VALID_ID.pattern}')
            continue
        if card_id in used_ids:
            errors.append(f'Card {idx}: duplicate id {card_id!r}')
        used_ids.add(card_id)
        kind = note.get('kind', 'concept')
        if not isinstance(kind, str) or not VALID_ID.fullmatch(kind):
            errors.append(f'Card {idx}: invalid kind {kind!r}')
            kind = 'concept'
        kind_tag = f'kind::{kind}'
        if kind_tag not in tags:
            tags.append(kind_tag)
        supporting = note.get('supporting_sources', [])
        if not isinstance(supporting, list) or any(
            not isinstance(s, dict) or not isinstance(s.get('file'), str) or not s['file'].strip()
            or not isinstance(s.get('location'), str) or not s['location'].strip()
            for s in supporting
        ):
            errors.append(f'Card {idx}: supporting_sources must be list of {{file, location}} objects')
            supporting = []
        for support in supporting:
            if Path(support['file']).is_absolute() or '..' in Path(support['file']).parts:
                errors.append(f'Card {idx}: supporting source must be course-relative: {support["file"]}')
        media = note.get('media', [])
        if not isinstance(media, list) or any(not isinstance(m, str) or not m for m in media):
            errors.append(f'Card {idx}: media must be a list of relative filenames')
            media = []
        refs = set(IMAGE.findall(front + back)) | set(SOUND.findall(front + back))
        if refs - {Path(m).name for m in media}:
            errors.append(f'Card {idx}: referenced media not declared in media: {sorted(refs - {Path(m).name for m in media})}')
        for ref in media:
            media_file = (media_root / ref).resolve()
            if not media_file.is_relative_to(media_root) or Path(ref).is_absolute():
                errors.append(f'Card {idx}: media path escapes output directory: {ref}')
                continue
            if media_file.suffix.lower() not in EXTS:
                errors.append(f'Card {idx}: unsupported media extension: {ref}')
            if not media_file.is_file():
                errors.append(f'Card {idx}: missing media: {ref}')
                continue
            base = media_file.name
            if base in media_paths and media_paths[base] != media_file:
                errors.append(f'Card {idx}: duplicate media basename {base}; use unique filenames')
            media_paths[base] = media_file
        # A filename used in Anki must be basename-only and safe.
        for ref in refs:
            if Path(ref).name != ref or ref.startswith('http:') or ref.startswith('https:'):
                errors.append(f'Card {idx}: media must use local basename, not URL/path: {ref}')
        key = (typ, compact(front))
        if front and key in seen_first:
            old = seen_first[key]
            if compact(back) != compact(old['back']):
                errors.append(f'Card {idx}: same question as card {old["index"]} but conflicting answers')
            else:
                duplicates += 1
            continue
        seen_first[key] = {'index': idx, 'back': back}
        normalized.append(dict(type=typ, id=card_id, front=front, back=back,
                               source_file=sf, source_location=sl, tags=tags,
                               media=media, kind=kind, supporting_sources=supporting))
    if errors:
        raise ValueError('Validation failed; no files written:\n' + '\n'.join(errors[:70]) +
                         (f'\n... and {len(errors) - 70} more' if len(errors) > 70 else ''))
    return deck, normalized, media_paths, legacy, duplicates, len(cards)


def source_html(note):
    pairs = [(note['source_file'], note['source_location'])] + [
        (x['file'], x['location']) for x in note['supporting_sources']]
    items = ' | '.join(f'{html.escape(a)} · {html.escape(b)}' for a, b in pairs)
    return f'<small class="lta-source">Source: {items}</small>'


def export_text(deck, cards, dst):
    rows = {'basic': [], 'cloze': []}
    for note in cards:
        first, second = field(note['front']), field(note['back'])
        source = source_html(note)
        rows[note['type']].append((first, second + '<br><br>' + source, ' '.join(note['tags'])))
    result = {}
    for typ, entries in rows.items():
        if not entries:
            continue
        cols = ('Front', 'Back', 'Tags') if typ == 'basic' else ('Text', 'Back Extra', 'Tags')
        header = ['#separator:Tab', '#html:true', '#notetype:' + ('Basic' if typ == 'basic' else 'Cloze'),
                  '#deck:' + deck, '#columns:' + '\t'.join(cols), '#tags column:3']
        path = dst / (typ + '.txt')
        path.write_text('\n'.join(header + ['\t'.join(row) for row in entries]) + '\n', encoding='utf-8')
        result[typ] = str(path)
    return result


def export_package(deck_name, cards, media, path):
    try:
        import genanki
    except ImportError as exc:
        raise ValueError('For .apkg export, install genanki: python3 -m pip install genanki\n'
                         'If you cannot install it, rerun with --format text.') from exc

    # IDs are deterministic; never generate random deck/model IDs on each export.
    deck = genanki.Deck(stable_number('deck', deck_name), deck_name)
    css = '.card {font-family:Arial,sans-serif;font-size:19px;text-align:left;line-height:1.45;} ' \
          '.lta-source {display:block;color:#888;margin-top:12px;font-size:12px;} ' \
          '.cloze {font-weight:bold;color:#2277bb;} img {max-width:95%;max-height:70vh;}'
    basic = genanki.Model(
        stable_number('model', deck_name, 'basic-v1'), 'Lecture-to-Anki Basic - ' + deck_name,
        fields=[{'name': n} for n in ['LTA_ID', 'Front', 'Back', 'Source']],
        templates=[{'name': 'Recall', 'qfmt': '{{Front}}',
                    'afmt': '{{FrontSide}}<hr id="answer">{{Back}}<br><br>{{Source}}'}],
        css=css, sort_field_index=1)
    cloze = genanki.Model(
        stable_number('model', deck_name, 'cloze-v1'), 'Lecture-to-Anki Cloze - ' + deck_name,
        fields=[{'name': n} for n in ['LTA_ID', 'Text', 'Extra', 'Source']],
        templates=[{'name': 'Cloze', 'qfmt': '{{cloze:Text}}',
                    'afmt': '{{cloze:Text}}<hr id="answer">{{Extra}}<br><br>{{Source}}'}],
        model_type=genanki.Model.CLOZE, css=css, sort_field_index=1)
    for card in cards:
        model = basic if card['type'] == 'basic' else cloze
        fields = [card['id'], card['front'], card['back'], source_html(card)]
        # Stable even when question, answer, media and source locations are edited.
        guid = genanki.guid_for('lecture-to-anki', deck_name, card['id'])
        note = genanki.Note(model=model, fields=fields, tags=card['tags'], guid=guid)
        deck.add_note(note)
    package = genanki.Package(deck)
    package.media_files = [str(p) for p in sorted(media.values())]
    package.write_to_file(str(path))


def commit_source_baseline(course: Path, dst: Path):
    from plan_update import inventory
    root = course.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f'Not a course folder: {root}')
    manifest = {'version': 1, 'course': str(root), 'files': inventory(root)}
    target = dst / 'source_manifest.json'
    temp = target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(target)
    return str(target)


def export(src: Path, dst: Path, fmt: str, course: Path | None):
    media_root = dst
    deck, cards, media, legacy, duplicates, input_notes = normalize_and_validate(src, media_root)
    # Determine prerequisites *before* creating output files.
    if fmt in {'apkg', 'both'}:
        try:
            import genanki  # noqa: F401
        except ImportError as exc:
            raise ValueError('genanki not installed. Run python3 -m pip install genanki, '
                             'or use --format text') from exc
    dst.mkdir(parents=True, exist_ok=True)
    files = {}
    if fmt in {'apkg', 'both'}:
        path = dst / 'deck.apkg'
        temp_path = path.with_suffix('.apkg.tmp')
        try:
            export_package(deck, cards, media, temp_path)
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
        files['apkg'] = str(path)
    if fmt in {'text', 'both'}:
        files.update(export_text(deck, cards, dst))
    report = {
        'deck': deck, 'input_notes': input_notes, 'exported_notes': len(cards),
        'basic': sum(n['type'] == 'basic' for n in cards),
        'cloze_notes': sum(n['type'] == 'cloze' for n in cards),
        'cloze_cards': sum(len(set(int(x) for x, _ in CLOZE.findall(n['front']))) for n in cards if n['type'] == 'cloze'),
        'exact_duplicate_notes_skipped': duplicates, 'notes_without_explicit_ids': legacy,
        'media_count': len(media), 'format': fmt, 'files': files,
        'warning': ('Text imports match first field and do NOT keep stable IDs when questions change. '
                    'Use .apkg consistently; do not import both formats into the same collection.')
    }
    (dst / 'export_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if course:
        report['source_manifest'] = commit_source_baseline(course, dst)
        (dst / 'export_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(cards)} notes, {report["cloze_cards"]} cloze cards, {len(media)} media assets.')
    for k, v in files.items():
        print(f'{k}: {v}')
    if legacy:
        print(f'WARNING: {legacy} legacy notes lack explicit IDs; migrate IDs before editing wording.', file=sys.stderr)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path, help='cards.json dataset')
    ap.add_argument('--output', type=Path, help='Output directory (defaults to input parent)')
    ap.add_argument('--course', type=Path, help='Course root for source_manifest.json snapshot after successful export')
    ap.add_argument('--format', choices=['both', 'apkg', 'text'], default='both')
    args = ap.parse_args()
    src = args.input.expanduser().resolve()
    dst = (args.output or src.parent).expanduser().resolve()
    try:
        export(src, dst, args.format, args.course)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
