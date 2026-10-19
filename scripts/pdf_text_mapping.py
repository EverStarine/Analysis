"""Supplement missing Adobe GB1 text mappings in a PDF reader's memory only.

Purpose: permit targeted text checks without modifying the source PDF.
Reassess the font matching and CMap location when the TeX installation or PDF
font encoding changes; this is an extraction aid, not a PDF font repair.
"""
from pathlib import Path
from pypdf.generic import DecodedStreamObject, NameObject

CMAP = Path('D:/texstudio/texlive/2025/texmf-dist/fonts/cmap/adobemapping/mapping-resources-pdf/pdf2unicode/Adobe-GB1-UCS2')

def supplement_gb1_text_mapping(reader, page_indices, cmap_path=None):
    cmap = Path(cmap_path) if cmap_path is not None else CMAP
    cmap_bytes = None
    patched = set()
    for i in page_indices:
        for ref in reader.pages[i]['/Resources'].get('/Font', {}).values():
            font = ref.get_object()
            if font.get('/ToUnicode') or not font.get('/DescendantFonts'):
                continue
            descendant = font['/DescendantFonts'][0].get_object()
            info = descendant.get('/CIDSystemInfo', {})
            if str(info.get('/Registry')) != 'Adobe' or str(info.get('/Ordering')) != 'GB1':
                continue
            if cmap_bytes is None:
                cmap_bytes = cmap.read_bytes()
            stream = DecodedStreamObject()
            stream.set_data(cmap_bytes)
            font[NameObject('/ToUnicode')] = stream
            patched.add(str(font.get('/BaseFont')))
    return {'source': str(cmap), 'fonts': sorted(patched), 'scope': 'Reader memory only; source PDF bytes are never written.'}
