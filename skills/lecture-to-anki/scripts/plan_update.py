#!/usr/bin/env python3
"""Diff course materials against the last *successful export* snapshot.

This script never changes cards or the baseline. Run before re-extracting sources,
then regenerate only affected topics and export to commit a new snapshot.
"""

import argparse
import json
import sys
from pathlib import Path

from extract_sources import KNOWN_UNSUPPORTED, SKIP_DIRS, SUPPORTED, VISUAL, classify, sha256_file


def inventory(root: Path):
    records = {}
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part.startswith('.') or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if path.suffix.lower() not in SUPPORTED | VISUAL | KNOWN_UNSUPPORTED:
            continue
        records[rel.as_posix()] = {
            'sha256': sha256_file(path),
            'category': classify(rel),
            'type': path.suffix.lower(),
        }
    return dict(sorted(records.items()))


def referenced_files(card):
    result = [card.get('source_file', '')]
    extra = card.get('supporting_sources', [])
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, dict):
                result.append(item.get('file', ''))
    return set(result)


def plan(root: Path, manifest: Path, cards_path: Path):
    current = inventory(root)
    old = {}
    initial = not manifest.exists()
    if not initial:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('files'), dict):
            raise ValueError('Invalid source_manifest.json (expected version 1 and files object)')
        old = data['files']
    new = sorted(set(current) - set(old))
    deleted = sorted(set(old) - set(current))
    changed = sorted(p for p in set(current) & set(old)
                     if current[p]['sha256'] != old[p]['sha256'])
    unchanged = sorted(p for p in set(current) & set(old)
                       if current[p]['sha256'] == old[p]['sha256'])
    affected = []
    if cards_path.exists():
        cards = json.loads(cards_path.read_text(encoding='utf-8')).get('cards', [])
        impacted = set(changed + deleted)
        for pos, card in enumerate(cards, 1):
            if referenced_files(card) & impacted:
                affected.append({'id': card.get('id', ''), 'index': pos,
                                 'source_file': card.get('source_file', ''),
                                 'affected_sources': sorted(referenced_files(card) & impacted)})
    return {
        'baseline_exists': not initial,
        'baseline': str(manifest),
        'new': new, 'changed': changed, 'deleted': deleted,
        'unchanged_count': len(unchanged),
        'affected_cards': affected,
        'summary': {'new': len(new), 'changed': len(changed), 'deleted': len(deleted),
                    'unchanged': len(unchanged), 'affected_cards': len(affected)},
        'instructions': (
            'No baseline yet: first generate the entire course, then export with --course.'
            if initial else
            'Inspect all new/changed documents; re-evaluate affected cards, preserve IDs; '
            'review cards with deleted sources instead of silently deleting them; '
            'export with --course to commit the new baseline.'
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('course', type=Path)
    ap.add_argument('--output', type=Path, help='Default: <course>/anki-output/update_plan.json')
    ap.add_argument('--manifest', type=Path, help='Default: <course>/anki-output/source_manifest.json')
    ap.add_argument('--cards', type=Path, help='Default: <course>/anki-output/cards.json')
    args = ap.parse_args()
    root = args.course.expanduser().resolve()
    if not root.is_dir():
        ap.error(f'Not a directory: {root}')
    output = (args.output or root / 'anki-output' / 'update_plan.json').expanduser().resolve()
    manifest = (args.manifest or root / 'anki-output' / 'source_manifest.json').expanduser().resolve()
    cards = (args.cards or root / 'anki-output' / 'cards.json').expanduser().resolve()
    try:
        result = plan(root, manifest, cards)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result['summary'], indent=2))
    print(f'Plan: {output}')


if __name__ == '__main__':
    main()
