#!/usr/bin/env python3
"""Add stable explicit IDs to a legacy cards.json once, keeping a .bak copy."""
import argparse
import json
import shutil
from pathlib import Path
from export_anki import legacy_id


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cards', type=Path)
    args = ap.parse_args()
    path = args.cards.expanduser().resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    updated = 0
    for card in data['cards']:
        if not card.get('id'):
            card['id'] = legacy_id(card['type'].lower(), card)
            updated += 1
    if updated:
        backup = path.with_suffix(path.suffix + '.bak')
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Added {updated} IDs to {path}; existing IDs unchanged.')


if __name__ == '__main__':
    main()
