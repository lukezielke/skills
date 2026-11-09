#!/usr/bin/env python3
"""Prepare local lecture figures for Anki media inclusion.

Examples:
  python prepare_media.py pdf slides/lecture3.pdf --page 5 --crop 100,90,490,340 --output anki-output/media
  python prepare_media.py pptx-slide slides/lecture3.pptx --slide 5 --output anki-output/media
  python prepare_media.py pptx-image slides/lecture3.pptx --slide 5 --image 1 --output anki-output/media
  python prepare_media.py image figures/graph.png --output anki-output/media

Report the generated basename in a card's <img src="basename.png"> field and
its path relative to anki-output/ in the card's media array.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.parse import unquote

RASTER = {'.png', '.jpg', '.jpeg', '.gif', '.svg'}


def fingerprint(name, payload):
    slug = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name)[:45]
    return 'lta_' + slug + '_' + hashlib.sha256(payload).hexdigest()[:14]


def store(source_name, raw: bytes, suffix: str, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    suffix = suffix.lower()
    if suffix in RASTER:
        content = raw
    else:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError('Non-PNG/JPEG/GIF image conversion needs Pillow: python3 -m pip install pillow') from exc
        import io
        with Image.open(io.BytesIO(raw)) as im:
            buf = io.BytesIO()
            im.convert('RGBA').save(buf, format='PNG')
            content = buf.getvalue()
        suffix = '.png'
    filename = fingerprint(source_name, content) + suffix
    dst = output / filename
    if not dst.exists():
        dst.write_bytes(content)
    return dst


def render_pdf(src: Path, page: int, crop: str | None, dpi: int, output: Path):
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('Rendering PDFs needs PyMuPDF: python3 -m pip install pymupdf') from exc
    with fitz.open(src) as doc:
        if page < 1 or page > len(doc):
            raise ValueError(f'Page out of range: {page} (PDF has {len(doc)})')
        p = doc[page - 1]
        clip = p.rect
        if crop:
            vals = [float(v.strip()) for v in crop.split(',')]
            if len(vals) != 4:
                raise ValueError('Crop must be x0,y0,x1,y1 in PDF points')
            rect = fitz.Rect(vals)
            clip = rect & p.rect
            if clip.is_empty or clip.is_infinite:
                raise ValueError('Crop is outside the page')
        pix = p.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), clip=clip,
                            alpha=False)
        raw = pix.tobytes('png')
        return store(f'{src.stem}_page{page}', raw, '.png', output)


def render_slide(src: Path, slide: int, dpi: int, output: Path):
    if not shutil.which('libreoffice') and not shutil.which('soffice'):
        raise RuntimeError('Full PPTX slide rendering needs LibreOffice (soffice). '
                           'Use pptx-image mode to extract embedded pictures instead.')
    binary = shutil.which('libreoffice') or shutil.which('soffice')
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        result = subprocess.run([binary, '-env:UserInstallation=file://' + str(tmpdir / 'lo_profile'),
                                 '--headless', '--convert-to', 'pdf', '--outdir', str(tmpdir), str(src)],
                                capture_output=True, text=True)
        pdf = tmpdir / (src.stem + '.pdf')
        if result.returncode != 0 or not pdf.exists():
            raise RuntimeError(f'LibreOffice conversion failed: {result.stderr or result.stdout}')
        return render_pdf(pdf, slide, None, dpi, output)


def extract_pptx_image(src: Path, slide: int, image_index: int, output: Path):
    slide_path = f'ppt/slides/slide{slide}.xml'
    rel_path = f'ppt/slides/_rels/slide{slide}.xml.rels'
    with zipfile.ZipFile(src) as zf:
        if slide_path not in zf.namelist() or rel_path not in zf.namelist():
            raise ValueError('PPTX slide or relationships missing')
        slide_xml = ET.fromstring(zf.read(slide_path))
        rel_xml = ET.fromstring(zf.read(rel_path))
        mapping = {r.attrib.get('Id'): r.attrib.get('Target') for r in rel_xml.iter()
                   if r.tag.endswith('Relationship') and 'image' in r.attrib.get('Type', '')}
        embed = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'
        blips = [n.attrib[embed] for n in slide_xml.iter()
                 if n.tag.endswith('}blip') and embed in n.attrib and n.attrib[embed] in mapping]
        if image_index < 1 or image_index > len(blips):
            raise ValueError(f'Image index {image_index} out of range (found {len(blips)} pictures)')
        target = mapping[blips[image_index - 1]]
        if target.startswith('/'):
            internal = target.lstrip('/')
        else:
            import posixpath
            internal = posixpath.normpath(posixpath.join('ppt/slides', target))
        internal = unquote(internal)
        if not internal.startswith('ppt/media/') or internal not in zf.namelist():
            raise ValueError(f'Unexpected media path: {internal}')
        return store(f'{src.stem}_slide{slide}_image{image_index}', zf.read(internal),
                     Path(internal).suffix, output)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['pdf', 'pptx-slide', 'pptx-image', 'image'])
    ap.add_argument('source', type=Path)
    ap.add_argument('--page', type=int)
    ap.add_argument('--slide', type=int)
    ap.add_argument('--image', type=int)
    ap.add_argument('--crop', help='PDF crop rectangle (PDF points) x0,y0,x1,y1')
    ap.add_argument('--dpi', type=int, default=145)
    ap.add_argument('--output', type=Path, required=True, help='Usually course/anki-output/media')
    args = ap.parse_args()
    src = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    try:
        if not src.is_file():
            raise ValueError(f'No such source file: {src}')
        if args.mode == 'pdf':
            if not args.page: raise ValueError('--page is required for PDF mode')
            result = render_pdf(src, args.page, args.crop, args.dpi, output)
        elif args.mode == 'pptx-slide':
            if not args.slide: raise ValueError('--slide is required for PPTX slide mode')
            result = render_slide(src, args.slide, args.dpi, output)
        elif args.mode == 'pptx-image':
            if not args.slide or not args.image:
                raise ValueError('--slide and --image are required for PPTX picture mode')
            result = extract_pptx_image(src, args.slide, args.image, output)
        else:
            result = store(src.stem, src.read_bytes(), src.suffix, output)
        print(f'Image: {result}')
        print(f'HTML: <img src="{result.name}">')
        print(f'JSON media entry (if output is anki-output/media): "media/{result.name}"')
    except (RuntimeError, ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
